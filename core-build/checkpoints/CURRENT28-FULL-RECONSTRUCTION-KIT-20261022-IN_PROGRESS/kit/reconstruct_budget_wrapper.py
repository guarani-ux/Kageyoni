"""Companion host budget checks; default preflight only, unchanged exact helper.

The root serial lane/resource decision precedes an explicit --execute invocation.
This script opens no native world/SQLite/Client and performs no remote effects.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, re, resource, shutil, sys, time, traceback

ROOT = Path(__file__).resolve().parent
HELPER = ROOT / 'reconstruct_continuation.py'
HELPER_SHA = '5db3d4d1bb40ddf95ebc5da2fb2e4129c921b1d82440bbf817ec99c69def3b27'
RECIPE = ROOT / 'continuation-reconstruction-recipe.json'
DELTA = ROOT / 'continuation-delta.zip'
PROVIDERS = ROOT / 'providers-current-host.json'
TARGET_BYTES = 469620062
PROCESS_BYTES = 256 * 1024**2
CGROUP_RESERVE = 512 * 1024**2
DISK_RESERVE = 1073741824
INITIAL_REQUIRED = 1744546492
CGROUP = Path('/sys/fs/cgroup')
MONITOR = {'checks': 0, 'minimum_estimated_available': None, 'maximum_process_peak_rss': 0, 'samples': []}
BASELINE_OOM = None
LAST_BUDGET = None
EMERGENCY = bytearray(1024**2)
OUT = None
PARTIAL = None

def sha(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NOATIME', 0))
    with os.fdopen(fd, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')

def kv(path):
    return {k: int(v) for k, v in (line.split() for line in path.read_text().splitlines())}

def metadata(path):
    s = path.lstat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mode=s.st_mode,
                uid=s.st_uid, gid=s.st_gid, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)

def budget(stage, entry=None):
    global BASELINE_OOM, LAST_BUDGET
    stats = kv(CGROUP / 'memory.stat')
    events = kv(CGROUP / 'memory.events')
    current = int((CGROUP / 'memory.current').read_text())
    maximum = int((CGROUP / 'memory.max').read_text())
    minimum = int((CGROUP / 'memory.min').read_text())
    low = int((CGROUP / 'memory.low').read_text())
    clean = max(0, stats['file'] - stats['shmem'] - stats['file_dirty']
                - stats['file_writeback'] - stats['file_mapped'] - stats['unevictable'])
    available = max(0, maximum - current) + clean
    # stat may lag the helper's buffered tell(); counting that lag as remaining is conservative.
    observed_output = PARTIAL.stat().st_size if PARTIAL is not None and PARTIAL.exists() else 0
    remaining = max(0, TARGET_BYTES - observed_output)
    free = shutil.disk_usage(ROOT).free
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    oom = {k: v for k, v in events.items() if k.startswith('oom')}
    if BASELINE_OOM is None:
        BASELINE_OOM = oom
    p = dict(stage=stage, entry=entry, monotonic_seconds=time.monotonic(),
             model='ROOT_ADOPTED_HOST_BOUNDED_CLEAN_UNMAPPED_NORMAL_FILESYSTEM_CACHE_INCLUDING_ACTIVE',
             planning_estimate_not_guaranteed_cache_reclamation=True,
             assumption='Clean unmapped non-shmem non-unevictable normal filesystem cache, including active_file, may be reclaimed under pressure; immediate or complete reclamation is not guaranteed.',
             kernel_reference='https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html',
             memory_current=current, memory_max=maximum, memory_stat=stats,
             memory_events=events, baseline_OOM_events=BASELINE_OOM,
             memory_min=minimum, memory_low=low,
             protection_scope='Current mounted cgroup only; ancestors outside mount not observable or claimed.',
             estimated_clean_unmapped_normal_filesystem_cache=clean,
             estimated_host_available=available, process_peak_rss=peak,
             hard_RLIMIT_AS=resource.getrlimit(resource.RLIMIT_AS),
             observed_partial_bytes=observed_output, remaining_output_bytes=remaining,
             tmpfs_free=free, output_reserve_bytes=DISK_RESERVE,
             cgroup_reserve_bytes=CGROUP_RESERVE, process_budget_bytes=PROCESS_BYTES,
             required_tmpfs_remaining_output_and_reserve=remaining + DISK_RESERVE,
             required_cgroup_remaining_output_readback_process_and_reserve=remaining + TARGET_BYTES + PROCESS_BYTES + CGROUP_RESERVE,
             unchanged_initial_required_peak=INITIAL_REQUIRED)
    LAST_BUDGET = p
    assert 2 * TARGET_BYTES + PROCESS_BYTES + CGROUP_RESERVE == INITIAL_REQUIRED
    assert minimum == low == 0, 'Nonzero cgroup protection requires root inspection'
    assert resource.getrlimit(resource.RLIMIT_AS) == (PROCESS_BYTES, PROCESS_BYTES)
    assert free >= remaining + DISK_RESERVE, 'Tmpfs remaining output/1GiB reserve insufficient'
    assert available >= remaining + TARGET_BYTES + PROCESS_BYTES + CGROUP_RESERVE, 'Host-bounded memory estimate insufficient'
    assert peak <= PROCESS_BYTES, 'Process peak RSS exceeds 256MiB allowance'
    assert oom == BASELINE_OOM, 'Cgroup OOM counters changed'
    MONITOR['checks'] += 1
    MONITOR['maximum_process_peak_rss'] = max(MONITOR['maximum_process_peak_rss'], peak)
    old = MONITOR['minimum_estimated_available']
    MONITOR['minimum_estimated_available'] = available if old is None else min(old, available)
    if MONITOR['checks'] == 1 or MONITOR['checks'] % 500 == 0:
        MONITOR['samples'].append(p)
    return p

def main():
    global OUT, PARTIAL, EMERGENCY
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Run only after root serial/resource GO; default performs preflight only')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9-]+', args.run_id)
    stem = ('execution-' if args.execute else 'preflight-') + args.run_id
    receipt = ROOT / (stem + '.json')
    failure = ROOT / (stem + '-failure.json')
    assert not receipt.exists() and not failure.exists(), 'Existing attempt reports preserved; choose an explicitly assigned new run-id'
    outdir = ROOT / ('full-reconstruction-' + args.run_id)
    OUT = outdir / 'Samsara_Core_Build_Continuation.zip'
    PARTIAL = OUT.with_name(OUT.name + '.partial')
    assert ROOT.is_relative_to(Path('/dev/shm')) and not ROOT.is_symlink()
    assert not outdir.exists(), 'Existing output directory preserved'
    before = metadata(HELPER)
    assert sha(HELPER) == HELPER_SHA
    recipe = json.loads(RECIPE.read_bytes())
    assert recipe['reconstruction_script']['sha256'] == HELPER_SHA
    assert recipe['target']['bytes'] == TARGET_BYTES
    try:
        resource.setrlimit(resource.RLIMIT_AS, (PROCESS_BYTES, PROCESS_BYTES))
        initial = budget('initial-preflight')
        # Loading this reviewed helper does not invoke its main() or import candidate code.
        spec = importlib.util.spec_from_file_location('exact_continuation_helper', HELPER)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        assert metadata(HELPER) == before and sha(HELPER) == HELPER_SHA
        after_load = budget('helper-loaded-no-reconstruction')
        if not args.execute:
            save_new(receipt, dict(status='PREFLIGHT_ONLY_PASS', full_reconstruction_executed=False,
                     helper_sha256=HELPER_SHA, helper_metadata_unchanged=True,
                     planned_output=str(OUT), output_directory_created=False,
                     exact_helper_reserve_argument=DISK_RESERVE, initial_budget=initial,
                     after_helper_load_budget=after_load, monitor=MONITOR,
                     native_DB_Client_Git_Library_effects=False))
            print(json.dumps(dict(status='PREFLIGHT_ONLY_PASS', receipt=str(receipt), full_reconstruction_executed=False)))
            return
        original_body = helper.check_body
        original_zip_open = helper.zipfile.ZipFile.open
        def checked_body(inputs, entry, consumer=None):
            budget('before-check_body', entry['path'])
            return original_body(inputs, entry, consumer)
        def checked_zip_open(self, name, mode='r', pwd=None, *, force_zip64=False):
            # Also covers each unchanged testzip() readback member, without replacing testzip.
            budget('before-zip-member-open', getattr(name, 'filename', str(name)))
            return original_zip_open(self, name, mode, pwd, force_zip64=force_zip64)
        helper.check_body = checked_body
        helper.zipfile.ZipFile.open = checked_zip_open
        outdir.mkdir()
        old_argv = sys.argv
        started = time.monotonic()
        try:
            sys.argv = [str(HELPER), '--recipe', str(RECIPE), '--delta', str(DELTA),
                        '--providers-json', str(PROVIDERS), '--output', str(OUT),
                        '--reserve-bytes', str(DISK_RESERVE)]
            helper.main()
        finally:
            sys.argv = old_argv
            helper.check_body = original_body
            helper.zipfile.ZipFile.open = original_zip_open
        final = budget('helper-returned-after-complete-CRC')
        assert metadata(HELPER) == before and sha(HELPER) == HELPER_SHA
        assert OUT.stat().st_size == TARGET_BYTES and sha(OUT) == recipe['target']['sha256']
        save_new(receipt, dict(status='BOUNDED_EXACT_RECONSTRUCTION_HELPER_RETURNED_PASS',
                 full_reconstruction_executed=True, helper_sha256=HELPER_SHA,
                 helper_metadata_unchanged=True, output=str(OUT), output_bytes=TARGET_BYTES,
                 output_sha256=recipe['target']['sha256'], exact_helper_reserve_argument=DISK_RESERVE,
                 initial_budget=initial, final_budget=final, monitor=MONITOR,
                 elapsed_seconds=time.monotonic()-started, automatic_retry=False,
                 partial_preserved=PARTIAL.exists(), native_DB_Client_Git_Library_effects=False))
        print(json.dumps(dict(status='BOUNDED_EXACT_RECONSTRUCTION_HELPER_RETURNED_PASS', receipt=str(receipt))))
    except BaseException:
        EMERGENCY = None
        save_new(failure, dict(status='FAILED_PRESERVED_NO_RETRY', traceback=traceback.format_exc(),
                 last_budget=LAST_BUDGET, monitor=MONITOR, output=str(OUT),
                 output_exists=OUT.exists(), partial_exists=PARTIAL.exists(),
                 partial_bytes=PARTIAL.stat().st_size if PARTIAL.exists() else None,
                 automatic_retry=False, deletion=False, native_DB_Client_Git_Library_effects=False))
        raise

if __name__ == '__main__':
    main()
