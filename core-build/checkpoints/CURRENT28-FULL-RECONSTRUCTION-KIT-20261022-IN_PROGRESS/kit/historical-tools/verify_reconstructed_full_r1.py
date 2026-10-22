"""Independent byte-only readback, invoked only after successful full-r1 helper exit."""
from pathlib import Path
import base64, hashlib, importlib.util, json, os, resource, traceback, zipfile
R = Path(__file__).resolve().parent
OUTPUT = R / 'full-reconstruction-full-r1/Samsara_Core_Build_Continuation.zip'
ORIGINAL = Path('/dev/shm/continuation-current28-lzma/Samsara_Core_Build_Continuation.zip')
BLOCK = 1024**2
def source(path):
    return os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NOATIME', 0)), 'rb')
def digest(path):
    with source(path) as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
def metadata(path):
    s = path.lstat()
    return dict(device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,mode=s.st_mode,
                uid=s.st_uid,gid=s.st_gid,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
def main():
    resource.setrlimit(resource.RLIMIT_AS, (256*1024**2, 256*1024**2))
    execution = json.loads((R/'execution-full-r1.json').read_bytes())
    assert execution['status'] == 'BOUNDED_EXACT_RECONSTRUCTION_HELPER_RETURNED_PASS'
    wrapper=R/'reconstruct_budget_wrapper.py'
    assert digest(wrapper)=='6222ff063eaffbb939ff8da926cf4ebd97ee35ca7729d88d035726e733c9a87f'
    spec=importlib.util.spec_from_file_location('readback_host_budget',wrapper)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    guard.OUT=OUTPUT;guard.PARTIAL=OUTPUT.with_name(OUTPUT.name+'.partial')
    guard.BASELINE_OOM=execution['final_budget']['baseline_OOM_events']
    guard.budget('independent-readback-initial')
    recipe = json.loads((R/'continuation-reconstruction-recipe.json').read_bytes())
    delta = R/'continuation-delta.zip'
    assert digest(delta) == recipe['delta']['sha256']
    before = {str(p):metadata(p) for p in [OUTPUT,ORIGINAL,delta]}
    with source(delta) as f, zipfile.ZipFile(f) as z:
        b=z.read(recipe['entry_map']['member'])
        assert hashlib.sha256(b).hexdigest() == recipe['entry_map']['sha256']
        entries=json.loads(b)
    assert len(entries)==12688
    assert OUTPUT.stat().st_size == ORIGINAL.stat().st_size == recipe['target']['bytes']
    assert digest(OUTPUT) == digest(ORIGINAL) == recipe['target']['sha256']
    files=dirs=raw_bytes=compressed_bytes=0
    with source(OUTPUT) as f, source(OUTPUT) as raw, zipfile.ZipFile(f) as z:
        assert len(z.namelist())==len(set(z.namelist()))==12688
        for i,e in zip(z.infolist(),entries,strict=True):
            guard.budget('independent-readback-member',i.filename)
            assert i.filename==e['path'] and i.is_dir()==e['is_directory']
            m=dict(date_time=list(i.date_time),compress_type=i.compress_type,
                   comment_base64=base64.b64encode(i.comment).decode(),
                   extra_base64=base64.b64encode(i.extra).decode(),create_system=i.create_system,
                   create_version=i.create_version,extract_version=i.extract_version,
                   flag_bits=i.flag_bits,volume=i.volume,internal_attr=i.internal_attr,
                   external_attr=i.external_attr,CRC=i.CRC)
            assert m==e['zip_metadata'] and i.header_offset==e['target_header_offset']
            assert i.file_size==e['body_bytes'] and i.compress_size==e['compressed_bytes']
            h=hashlib.sha256();count=0
            with z.open(i) as member:
                for b in iter(lambda:member.read(BLOCK),b''):
                    h.update(b);count+=len(b)
            # zipfile checks member CRC when this stream reaches EOF.
            assert count==e['body_bytes'] and h.hexdigest()==e['body_sha256'],i.filename
            raw.seek(i.header_offset+e['local_header_bytes']);left=i.compress_size;h=hashlib.sha256()
            while left:
                b=raw.read(min(left,BLOCK));assert b;h.update(b);left-=len(b)
            assert h.hexdigest()==e['compressed_sha256'],i.filename
            dirs+=i.is_dir();files+=not i.is_dir();raw_bytes+=count;compressed_bytes+=i.compress_size
        assert hashlib.sha256(z.read('samsara_core/MANIFEST.json')).hexdigest()==recipe['current_gate_identity']['manifest_sha256']
        assert hashlib.sha256(z.read('samsara_core/BUILD_STATUS.json')).hexdigest()==recipe['current_gate_identity']['ledger_sha256']
    providers=json.loads((R/'providers-current-host.json').read_bytes())
    for p in recipe['providers']:
        guard.budget('independent-provider-after-readback',p['id'])
        path=Path(providers[p['id']]);assert path.stat().st_size==p['bytes'] and digest(path)==p['sha256'],p['id']
    after={str(p):metadata(p) for p in [OUTPUT,ORIGINAL,delta]}
    assert before==after
    assert files==11330 and dirs==1358 and raw_bytes==2790921522
    proof=dict(status='INDEPENDENT_FULL_RECONSTRUCTION_READBACK_PASS',output=str(OUTPUT),
               bytes=OUTPUT.stat().st_size,sha256=recipe['target']['sha256'],entries=12688,
               files=files,directories=dirs,raw_file_bytes=raw_bytes,compressed_body_bytes=compressed_bytes,
               all_member_decoded_SHA_CRC_metadata_modes_offsets_and_compressed_SHA=True,
               all_14_raw_provider_SHA_after_readback=True,original_b13_full_SHA_equal=True,
               output_original_delta_metadata_before_after_equal=True,metadata_before=before,
               hard_RLIMIT_AS=resource.getrlimit(resource.RLIMIT_AS),peak_RSS=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
               helper_execution_receipt='execution-full-r1.json',second_extraction=False,
               host_budget_monitor=guard.MONITOR,final_host_budget=guard.budget('independent-readback-final'),
               native_DB_Client_Git_Library_effects=False,new_remote_custody=False,new_Library_version=False)
    with (R/'independent-full-r1-readback.json').open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
    print(json.dumps(proof))
if __name__=='__main__':
    try:main()
    except BaseException:
        with (R/'independent-full-r1-readback-failure.txt').open('x') as f:f.write(traceback.format_exc())
        raise
