from pathlib import Path
from contextlib import ExitStack
import json,hashlib,zipfile,stat,base64,shutil,os,fcntl
R=Path('/workspace/scratch/5c7ed9200168/recovery-20261022');B=R/'github-product28-qualified-bounded'
def sha(x):return hashlib.sha256(x).hexdigest()
def git(x):return hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest()
def save(n,x):(B/n).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def meta(p):
 assert p.resolve()==p and (p.is_file() or p.is_dir());s=p.stat();r={'source':str(p),'kind':'dir' if p.is_dir() else 'file','mode':stat.S_IMODE(s.st_mode)}
 if p.is_file():
  h=hashlib.sha256()
  with p.open('rb') as f:
   for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
  r.update(bytes=s.st_size,sha256=h.hexdigest())
 return r
def makezip(path,rows):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,v in sorted(rows.items()):
   i=zipfile.ZipInfo(n,date_time=(1980,1,1,0,0,0));i.create_system=3;i.external_attr=((stat.S_IFDIR if v['kind']=='dir' else stat.S_IFREG)|v['mode'])<<16;i.compress_type=zipfile.ZIP_DEFLATED
   if v['kind']=='dir':z.writestr(i,b'');continue
   h=hashlib.sha256();count=0
   with Path(v['source']).open('rb') as f,z.open(i,'w') as target:
    for x in iter(lambda:f.read(1024*1024),b''):target.write(x);h.update(x);count+=len(x)
   assert count==v['bytes'] and h.hexdigest()==v['sha256'],n
  z.writestr('CHECKPOINT-MANIFEST.json',(json.dumps(rows,sort_keys=True,indent=2)+'\n').encode())
def provider(key,p):
 raw=p.read_bytes();members=[]
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  for i in z.infolist():members.append({'path':i.filename,'bytes':i.file_size,'sha256':sha(z.read(i)),'mode':stat.S_IMODE(i.external_attr>>16),'dir':i.is_dir()})
 parts=[];(B/(key+'-parts')).mkdir()
 for idx,off in enumerate(range(0,len(raw),500000)):
  x=raw[off:off+500000];a=base64.b64encode(x);n=f'{key}-parts/part-{idx:03}.base64';(B/n).write_bytes(a);parts.append({'path':n,'offset':off,'bytes':len(x),'sha256':sha(x),'raw_git_sha1':git(x),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)})
 r={'filename':p.name,'bytes':len(raw),'sha256':sha(raw),'zip_entries':len(members),'members':members,'parts':parts,'format':'exact-ASCII500000-raw-provider/1','scope':'Bounded EOF fix qualified ONLY; fullF1-F5 false; byte custody independent of semantics'};save(key+'-recipe.json',r);return r
def critical():
 assert shutil.disk_usage(B).free>2*1024**3;rows={}
 def add(p):
  n=str(p.relative_to(R));v=meta(p);assert v['kind']=='file';target=B/'snapshot'/n;target.parent.mkdir(parents=True,exist_ok=True);x=p.read_bytes();assert sha(x)==v['sha256'];target.write_bytes(x);os.chmod(target,v['mode']);v['original']=v['source'];v['source']=str(target);rows[n]=v
 for n in ['BUILD_STATUS.json','product28-bounded-semantic-receipt.json','product28-bounded-semantic-review.py','CONTINUATION-AFTER-PRODUCT28.md','prompt28-update-receipt.json','product28-build/receive_owner_loss_28.py','product28-build/receiving-r1.log','product28-build/installed-before.json','product28-build/installed_proof28.py','product28-build/final-source-manifest.json']:add(R/n)
 assert rows['BUILD_STATUS.json']['sha256']=='a813516c829f7e518d4c9a216713a6f89233abb06fe258aedd9d48d755c5b159'
 assert rows['product28-bounded-semantic-receipt.json']['sha256']=='a114430038773a3edfba912b03865ea159e9c79353c9a0223a4acce2198ccd8f'
 for root in ['product28-genuine-affected-r1','product28-actual-queue-fixture','product28-receiving-r1/fresh-receiving']:
  for p in sorted((R/root).rglob('*')):
   if p.is_file() and p.suffix!='.sqlite':add(p)
 old=R/'github-product28-r3';src=json.loads((old/'source-recipe.json').read_bytes());manifest=json.loads((R/'product28-build/final-source-manifest.json').read_bytes())
 for n,v in manifest['files'].items():
  p=R/'product28-build/package'/n;assert p.stat().st_size==v['bytes'] and sha(p.read_bytes())==v['sha256']
 for n,h in [('samsara_world-0.5.3.dev28-py3-none-any.whl','7360f0b41ed2691abab83bbfaf245eb61215b09f8c4a39fe3ce8a857efff4d4b'),('kageyoni_engine-11.1.0.dev16-py3-none-any.whl','845d7b4aaa3b81c66364eed09d34e91b57e5c0f99df6aaa654b470d4a1db4ff3')]:assert sha((R/'product28-build/distributions'/n).read_bytes())==h
 save('source-provider.json',{'repository':'guarani-ux/SAMSARA','immutable_commit':'3b62d8735f12f5b2a1852506b4000b95e2e4b4f8','checkpoint':'core-build/checkpoints/PRODUCT28-R3-20261022-IN_PROGRESS','recipe':'source-recipe.json','provider':{k:src[k] for k in ['filename','bytes','sha256','zip_entries']},'current38_source_files_and_both_wheels_independently_rechecked':True,'source_authoring_status_is_historical':'New bounded semantic receipt and current frozen BUILD_STATUS override prior authoring status only within explicit qualified EOF scope.'})
 save('selected-source-manifest.json',rows);p=B/'Product28_Bounded_Qualification_Evidence_IN_PROGRESS.zip';makezip(p,rows);r=provider('critical',p)
 context={'status':'QUALIFIED_BOUNDED_UNFED_EOF_EXIT_FIX_ONLY','fullF1_F5':False,'whole_D15b_or_full_release':False,'candidate':json.loads((B/'snapshot/product28-bounded-semantic-receipt.json').read_bytes())['candidate'],'source_provider':'source-provider.json','critical_provider':{k:r[k] for k in ['filename','bytes','sha256','zip_entries']},'body_status':'Pending full raw capture/upload. No body custody claimed until final BODY_READBACK receipt.','historical_failures':'Original27 failed registration, original28 fake fairness return rejection, earlier native journal/copied-world/overlay failures remain unchanged.','observation_limits':'27 mixed predicates2genuine+18old+7private passed; NOT clean original20 suite. Source-frameobserver0;1246 actualAPI/wire/lifecycle events retained. One matching currenthost/trustedworker lane.','prompt_update':'CONTINUATION-AFTER-PRODUCT28.md and prompt28-update-receipt.json are historical actual update evidence, not a new automation mutation. New semantic receipt overrides prompt authoring status.','excluded':['active f3a-native source','product28-custody-control-proposal source'],'still_NOT_RUN':['historical unknown-absence RECOVER','new dual real SIGKILL custody transaction seams']};save('context.json',context)
 direct=[{'path':n,'local':str(B/n)} for n in ['source-provider.json','selected-source-manifest.json','critical-recipe.json','context.json']]+[{'path':'selected/'+n,'local':v['source']} for n,v in rows.items()]
 for i,v in enumerate(direct):
  x=Path(v['local']).read_bytes();t=B/'upload-text'/f'critical-{i}.base64';t.parent.mkdir(exist_ok=True);t.write_bytes(base64.b64encode(x));v.update(bytes=len(x),sha256=sha(x),git_sha1=git(x),transport=str(t))
 save('direct-stage-files.json',direct);print(json.dumps({'source_files':len(rows),'critical':{k:r[k] for k in ['filename','bytes','sha256','zip_entries']},'parts':len(r['parts']),'direct':len(direct)},indent=2))
def body():
 assert shutil.disk_usage(B).free>2*1024**3;baseline=json.loads((B/'snapshot/product28-genuine-affected-r1/readonly-postconditions.json').read_bytes());roots={};expected={}
 for e in baseline['worlds']:
  p=Path(e['world']);label='mixed-27-worlds/'+str(p.relative_to('/dev/shm/p28real-r1'));roots[label]=p;expected[label]=e['before_manifest']
 roots['receiving-evidence']=R/'product28-receiving-r1';roots['physically-relocated-world']=Path('/dev/shm/p28move-r1/world')
 locks=[Path(e['world']) for e in baseline['worlds']]+[R/'product28-receiving-r1/final-closed-world',Path('/dev/shm/p28move-r1/world')]
 def catalog():
  rows={}
  for label,p in roots.items():
   for item in [p]+sorted(p.rglob('*')):
    rel=str(item.relative_to(p));n=label+('/' if rel=='.' else '/'+rel);v=meta(item);n+=('/' if v['kind']=='dir' and not n.endswith('/') else '');assert n not in rows;rows[n]=v
  return rows
 with ExitStack() as stack:
  receipts=[]
  for w in locks:
   fd=os.open(w/'owner.lock',os.O_RDONLY|os.O_NOFOLLOW);stack.callback(os.close,fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);stack.callback(fcntl.flock,fd,fcntl.LOCK_UN);receipts.append({'world':str(w),'existing_readonly_exclusive_owner_lock':True,'inode':os.fstat(fd).st_ino})
  rows=catalog()
  for label,manifest in expected.items():
   actual={n[len(label)+1:]:{k:v[k] for k in ['bytes','sha256']} for n,v in rows.items() if n.startswith(label+'/') and v['kind']=='file'};assert actual==manifest,label
  save('body-source-before.json',rows);p=B/'Product28_27_Closed_RAM_Worlds_and_Fresh_Recipient_Raw_IN_PROGRESS.zip';makezip(p,rows);after=catalog();assert rows==after;save('body-source-after.json',after)
  save('body-capture-result.json',{'status':'COMPLETE_RAW_BYTE_CAPTURE_ONLY','owner_lock_receipts':receipts,'world_trees':29,'mixed_worlds_prior27_manifests_equal':True,'source_before_after_bytes_modes_kinds_equal':True,'files':sum(v['kind']=='file' for v in rows.values()),'directories':sum(v['kind']=='dir' for v in rows.values()),'source_bytes':sum(v.get('bytes',0) for v in rows.values()),'DB_native_or_candidate_imports_or_opens':False})
 r=provider('body',p);print(json.dumps({'body':{k:r[k] for k in ['filename','bytes','sha256','zip_entries']},'parts':len(r['parts']),'worlds':29,'free':shutil.disk_usage(B).free},indent=2))
if __name__=='__main__':
 import sys
 {'critical':critical,'body':body}[sys.argv[1]]()
