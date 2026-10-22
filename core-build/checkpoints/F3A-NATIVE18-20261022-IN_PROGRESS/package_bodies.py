"""Byte custody only: no candidate imports, SQLite/native operations or processes."""
from pathlib import Path
from contextlib import ExitStack
import json,hashlib,zipfile,stat,base64,shutil,os,fcntl
R=Path('/workspace/scratch/5c7ed9200168/recovery-20261022');B=R/'github-native18-future'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def save(p,v):
 assert not p.exists(),str(p)
 p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def meta(p):
 s=p.lstat();mode=stat.S_IMODE(s.st_mode);common={'mode':mode,'inode':s.st_ino,'device':s.st_dev,'mtime_ns':s.st_mtime_ns}
 if stat.S_ISLNK(s.st_mode):
  target=os.readlink(p);b=os.fsencode(target);return dict(common,kind='symlink',target=target,bytes=len(b),sha256=sha(b))
 if stat.S_ISDIR(s.st_mode):return dict(common,kind='dir')
 assert stat.S_ISREG(s.st_mode),str(p)
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return dict(common,kind='file',bytes=s.st_size,sha256=h.hexdigest())
def provider(key,path):
 before=meta(path);members=[]
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  for i in z.infolist():
   b=z.read(i);typ=stat.S_IFMT(i.external_attr>>16)
   assert typ in (0,stat.S_IFREG,stat.S_IFDIR,stat.S_IFLNK),(i.filename,typ)
   members.append({'path':i.filename,'bytes':len(b),'sha256':sha(b),'mode':stat.S_IMODE(i.external_attr>>16),'file_type':typ,'dir':i.is_dir(),'symlink_target':os.fsdecode(b) if typ==stat.S_IFLNK else None})
 d=B/(key+'-parts');d.mkdir();parts=[];off=0
 with path.open('rb') as f:
  for idx,b in enumerate(iter(lambda:f.read(500000),b'')):
   a=base64.b64encode(b);n=f'{key}-parts/part-{idx:03}.base64';(B/n).write_bytes(a);parts.append({'path':n,'offset':off,'bytes':len(b),'sha256':sha(b),'raw_git_sha1':git(b),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)});off+=len(b)
 assert meta(path)==before
 r={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':before['bytes'],'sha256':before['sha256'],'zip_entries':len(members),'members':members,'parts':parts,'source_archive_metadata_before':before,'source_archive_metadata_after':meta(path),'scope':'Byte custody only. Negative/stopped worlds remain negative/unknown; no DB health/native/product/F3/full-release claim.'};save(B/(key+'-recipe.json'),r)
 return {k:r[k] for k in ['filename','bytes','sha256','zip_entries']}|{'parts':len(parts)}
def archives():
 results={};d=B/'raw';d.mkdir(exist_ok=True)
 for key,name,size,h,count in [('native17','f3a-root-integration/native17-closed-raw/Native17_37_API_and_6_Review_Regression_Raw.zip',63842950,'deb9cf49b8ec4c642d63dd1629e9a76af91064c6f20f10ea2f3de9a60a14d45f',1468),('native18','f3a-root-integration-r2/native18-closed-raw-r2/Native18_43_API_2_Fork_and_Preserved_Harness_Failure_Raw.zip',68360077,'9aad54982fd63273c30a9514d3a65b7d1878a8eeb77a7e7f4a6c2b11ebdcf3d9',1569)]:
  p=R/name;before=meta(p);assert before['bytes']==size and before['sha256']==h and before['kind']=='file';target=d/p.name
  if target.exists():
   old=json.loads((B/(key+'-archive-copy-proof.json')).read_bytes());assert before==old['source_before']==old['source_after'] and meta(target)==old['copy_metadata']
  else:shutil.copy2(p,target)
  after=meta(p);copied=meta(target);assert before==after and all(before[k]==copied[k] for k in ('kind','bytes','sha256','mode','mtime_ns'))
  if not (B/(key+'-archive-copy-proof.json')).exists():save(B/(key+'-archive-copy-proof.json'),{'source':str(p),'copy':str(target),'source_before':before,'source_after':after,'copy_metadata':copied,'exact_bytes_mode_mtime':True,'DB_opened':False})
  r=provider(key,target);assert r['zip_entries']==count;results[key]=r
 save(B/'native-archives-result.json',results);print(json.dumps(results,indent=2),flush=True)
def supplemental():
 roots={'native18-copy-maintenance':R/'f3a-root-integration-r2/real-copy-maintenance','stopped-control-complete':R/'product28-custody-control-proposal'}
 singles=[R/'f3a-root-integration-r2'/n for n in ['maintain_real_copy.py','maintenance-predecessor.log','maintenance-successor.log','check_fork_boundary.py','check_fork_boundary_r2.py','fork-boundary-r1.log','fork-boundary-r2.log','capture_closed_native.py','capture_closed_native_r2.py','native18-capture.log','native18-capture-r2.log']]
 for sub in ['f3a-root-integration/native17-closed-raw','f3a-root-integration-r2/native18-closed-raw','f3a-root-integration-r2/native18-closed-raw-r2']:
  for p in sorted((R/sub).iterdir()):
   if p.is_file() and p.suffix!='.zip':singles.append(p)
 # The first bad helper and its raw worlds also remain in the exact native18 ZIP.
 for sub in ['fork-boundary-r1','fork-boundary-r2']:
  p=R/'f3a-root-integration-r2'/sub
  if p.exists():roots[sub]=p
 def catalog():
  rows={}
  for label,root in roots.items():
   for p in [root]+sorted(root.rglob('*')):
    v=meta(p);rel=str(p.relative_to(root));n=label+('/' if rel=='.' else '/'+rel);n+=('/' if v['kind']=='dir' and not n.endswith('/') else '');assert n not in rows;rows[n]={'source':str(p),**v}
  for p in singles:rows['maintenance-harness-and-custody/'+str(p.relative_to(R))]={'source':str(p),**meta(p)}
  return rows
 lockpaths=[]
 for root in roots.values():
  for p in sorted(root.rglob('owner.lock')):
   assert p.is_file() and not p.is_symlink();lockpaths.append(p)
 with ExitStack() as stack:
  locks=[]
  for p in sorted(set(lockpaths)):
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);stack.callback(os.close,fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);stack.callback(fcntl.flock,fd,fcntl.LOCK_UN);locks.append({'path':str(p),'inode':os.fstat(fd).st_ino,'existing_readonly_exclusive_nonblocking':True})
  before=catalog();save(B/'supplemental-source-before.json',before);path=B/'Native18_Copy_Maintenance_and_Stopped_Control_Raw_IN_PROGRESS.zip'
  with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for n,v in sorted(before.items()):
    kind={'dir':stat.S_IFDIR,'file':stat.S_IFREG,'symlink':stat.S_IFLNK}[v['kind']];i=zipfile.ZipInfo(n,(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(kind|v['mode'])<<16;i.compress_type=zipfile.ZIP_DEFLATED
    if v['kind']=='dir':z.writestr(i,b'');continue
    if v['kind']=='symlink':b=os.fsencode(os.readlink(v['source']));assert sha(b)==v['sha256'];z.writestr(i,b);continue
    h=hashlib.sha256();size=0
    with Path(v['source']).open('rb') as f,z.open(i,'w') as target:
     for b in iter(lambda:f.read(1024*1024),b''):target.write(b);h.update(b);size+=len(b)
    assert size==v['bytes'] and h.hexdigest()==v['sha256'],n
   i=zipfile.ZipInfo('CHECKPOINT-MANIFEST.json',(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|0o600)<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,(json.dumps(before,indent=2,sort_keys=True)+'\n').encode())
  after=catalog();assert before==after;save(B/'supplemental-source-after.json',after);save(B/'supplemental-capture-result.json',{'status':'COMPLETE_BYTE_CUSTODY_ONLY','roots':{k:str(v) for k,v in roots.items()},'singles':[str(p) for p in singles],'locks':locks,'source_entries':len(before),'source_bytes':sum(v.get('bytes',0) for v in before.values()),'source_before_after_metadata_exact':True,'sqlite_or_native_opened':False,'all_negative_worlds_healthy':False})
 result=provider('supplemental',path);save(B/'supplemental-result.json',result);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':
 import sys
 {'archives':archives,'supplemental':supplemental}[sys.argv[1]]()
