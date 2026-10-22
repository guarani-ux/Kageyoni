"""Proposed bounded byte-only Git readback adapter. No candidate/native/DB imports."""
from pathlib import Path,PurePosixPath
import argparse,base64,hashlib,json,os,stat,sys,zipfile
B=Path('/dev/shm/github-product32-attachment-award')
D=B/'streaming-body'
LIMIT=18*1024*1024  # operational cap; leaves2MiB for boundedfinal/ref receipts
INPUT_LIMIT=2*1024*1024
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:
  json.dump(v,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def meta(p):
 s=p.lstat();assert stat.S_ISREG(s.st_mode) and not p.is_symlink(),str(p)
 return dict(path=str(p),device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,mode=stat.S_IMODE(s.st_mode),mtime_ns=s.st_mtime_ns,bytes=s.st_size,allocated_bytes=s.st_blocks*512)
def allocated():
 return sum(p.lstat().st_blocks*512 for p in D.rglob('*') if p.is_file())
def budget(add=0):
 v=allocated();assert v+add<=LIMIT,(v,add,LIMIT);return v
def exact_source(x):
 p=Path(x['local']);a=meta(p);v=p.read_bytes();assert meta(p)==a
 assert len(v)==x['bytes'] and sha(v)==x['sha256'] and git(v)==x['git_sha1'],x['path']
 return p,a,v
p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','value','archives'])
p.add_argument('--plan',type=Path);p.add_argument('--index',type=int);p.add_argument('--input',type=Path)
p.add_argument('--label',required=True);p.add_argument('--receipt',type=Path,required=True)
p.add_argument('--reserve-bytes',type=int,default=2*1024*1024)
a=p.parse_args()
assert a.receipt.is_relative_to(D) and not a.receipt.exists()
D.mkdir(exist_ok=True)
if a.action=='preflight':
 rows=json.loads(a.plan.read_bytes());assert len(rows)<256
 if a.index is None:check_rows=rows
 else:assert 0<=a.index<len(rows);check_rows=[rows[a.index]]
 for x in check_rows:exact_source(x)
 assert 0<=a.reserve_bytes<=INPUT_LIMIT
 v=dict(status='PLAN_CANONICAL_VALUES_FULL_BYTES_AND_METADATA_VERIFIED',plan=str(a.plan),plan_sha256=sha(a.plan.read_bytes()),values=len(rows),current_streaming_allocated=budget(a.reserve_bytes),reserved_incoming=a.reserve_bytes,new_phase_limit=LIMIT,incoming_limit=INPUT_LIMIT)
 save(a.receipt,v);print(json.dumps(v));sys.exit(0)
if a.action=='value':
 assert a.input.is_relative_to(D/'incoming') and a.input.is_file()
 assert a.input.stat().st_size<=INPUT_LIMIT
 budget(16384)
 rows=json.loads(a.plan.read_bytes());x=rows[a.index]
 im=meta(a.input);raw=a.input.read_bytes();assert meta(a.input)==im
 try:
  e=json.loads(raw);assert set(e)=={'index','actual_value_base64'} and e['index']==a.index
  actual=base64.b64decode(e['actual_value_base64'],validate=True)
  canonical,cm,expected=exact_source(x)
  assert actual==expected,'ACTUAL_REMOTE_VALUE_DIFFERS_CANONICAL'
  assert len(actual)==x['bytes'] and sha(actual)==x['sha256'] and git(actual)==x['git_sha1']
  assert meta(canonical)==cm and meta(a.input)==im
  v=dict(status='ACTUAL_REMOTE_FULL_VALUE_EXACT',label=a.label,index=a.index,repo=x['repo'],path=x['path'],actual_bytes=len(actual),actual_sha256=sha(actual),actual_git_sha1=git(actual),expected_git_sha1=x['git_sha1'],canonical=cm,canonical_sha256=sha(expected),input_transport=im,input_transport_sha256=sha(raw),plan_sha256=sha(a.plan.read_bytes()),full_input_value_not_truncated=True,no_decoded_body_copy_written=True,successful_transport_release_issued=True,current_streaming_allocated=budget())
  save(a.receipt,v)
  # Only this newly-derived successful transport envelope is released.
  # Its complete decoded value is equal to the still-retained canonical file;
  # mismatches/errors remain intact. Original sources/parts are never unlinked.
  assert meta(canonical)==cm and canonical.read_bytes()==actual
  assert meta(a.input)==im
  a.input.unlink()
  assert not a.input.exists()
  assert meta(canonical)==cm and sha(canonical.read_bytes())==x['sha256']
  save(a.receipt.with_suffix('.released.json'),dict(status='SUCCESSFUL_DERIVED_TRANSPORT_RELEASE_CONFIRMED',input=str(a.input),input_metadata=im,input_sha256=sha(raw),proof=str(a.receipt),proof_sha256=sha(a.receipt.read_bytes()),retained_canonical_after=meta(canonical),retained_canonical_sha256=x['sha256'],allocated_after=budget()))
  print(json.dumps(dict(ok=True,index=a.index,repo=x['repo'],path=x['path'],bytes=len(actual),GitID=git(actual),transport_released=True)))
 except Exception as ex:
  f=a.receipt.with_suffix('.FAIL.json')
  if not f.exists():save(f,dict(status='STOP_PRESERVE_ACTUAL_INPUT_NO_RETRY',error=repr(ex),index=a.index,repo=x['repo'],path=x['path'],input=str(a.input),input_exists=a.input.exists(),input_sha256=sha(raw)))
  raise
 sys.exit(0)
# Final archive proof derives actual remote ZIP equality from every full actual
# ASCII value, exact coverage, retained immutable parts and carrier byte ranges.
rows=json.loads(a.plan.read_bytes())
plan_hash=sha(a.plan.read_bytes())
receipts=[json.loads(q.read_bytes()) for q in (D/a.label/'values').glob('*.json') if not q.name.endswith(('.released.json','.FAIL.json'))]
assert len(receipts)==len(rows),(len(receipts),len(rows))
assert {r['index'] for r in receipts}==set(range(len(rows)))
for r in receipts:
 x=rows[r['index']];assert r['status']=='ACTUAL_REMOTE_FULL_VALUE_EXACT' and r['repo']==x['repo'] and r['path']==x['path'] and r['actual_git_sha1']==x['git_sha1'] and r['plan_sha256']==plan_hash
 exact_source(x)
proven={(r['repo'],r['path']):r for r in receipts}
all_archive=[]
for kind,carrier in [('body',B/'Product32_Attachment_Play_Award_Complete_Packet_IN_PROGRESS.zip'),('raw',Path('/dev/shm/product32-checkpoint/Product32_Play_Award_Failure_Withdrawal_Raw.zip'))]:
 recipe=json.loads((B/(kind+'-recipe.json')).read_bytes());cm=meta(carrier);count=0
 with carrier.open('rb') as f:
  for part in recipe['parts']:
   pr=proven[('SAMSARA',part['path'])]
   ascii_bytes=(B/part['path']).read_bytes()
   assert len(ascii_bytes)==part['ASCII_bytes'] and sha(ascii_bytes)==part['ASCII_sha256'] and git(ascii_bytes)==part['git_sha1']==pr['actual_git_sha1']
   chunk=base64.b64decode(ascii_bytes,validate=True)
   assert count==part['offset'] and len(chunk)==part['bytes'] and sha(chunk)==part['sha256'] and git(chunk)==part['raw_git_sha1']
   assert f.tell()==count and f.read(len(chunk))==chunk
   count+=len(chunk)
  assert f.read(1)==b''
 assert count==recipe['bytes'] and meta(carrier)==cm
 h=hashlib.sha256()
 with carrier.open('rb') as f:
  for d in iter(lambda:f.read(1024*1024),b''):h.update(d)
 assert h.hexdigest()==recipe['sha256']
 with zipfile.ZipFile(carrier) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==recipe['zip_entries']
  assert set(z.namelist())=={m['path'] for m in recipe['members']}
  for m in recipe['members']:
   i=z.getinfo(m['path']);typ=stat.S_IFMT(i.external_attr>>16)
   assert not PurePosixPath(i.filename).is_absolute() and '..' not in PurePosixPath(i.filename).parts
   mh=hashlib.sha256();mc=0;target=[]
   with z.open(i) as member:
    for d in iter(lambda:member.read(1024*1024),b''):
     mh.update(d);mc+=len(d)
     if typ==stat.S_IFLNK:assert mc<=1024*1024;target.append(d)
   assert mc==m['bytes'] and mh.hexdigest()==m['sha256'] and stat.S_IMODE(i.external_attr>>16)==m['mode'] and typ==m['file_type'] and i.is_dir()==m['dir']
   assert (os.fsdecode(b''.join(target)) if typ==stat.S_IFLNK else None)==m['symlink_target']
 assert meta(carrier)==cm
 all_archive.append(dict(kind=kind,retained_usable_carrier=cm,actual_remote_complete_coverage_equal_retained_carrier=True,bytes=count,sha256=h.hexdigest(),ASCII_actual_remote_parts=len(recipe['parts']),ZIP_members=recipe['zip_entries'],all_CRC_memberSHA_mode_type_symlinktargets_exact=True,no_second_full_ZIP_written=True))
v=dict(status='ACTUAL_REMOTE_COMPLETE_ARCHIVE_BYTES_EQUAL_RETAINED_USABLE_CARRIERS',archives=all_archive,actual_full_value_receipts=len(receipts),own_new_streaming_allocated=budget(),own_new_phase_limit=LIMIT,no_DB_native_Client_build_test_world_effects=True)
save(a.receipt,v);print(json.dumps(v))

