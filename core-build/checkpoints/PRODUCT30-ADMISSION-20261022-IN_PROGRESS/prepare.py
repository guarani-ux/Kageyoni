"""Frozen-packet byte packaging only; no candidate or native imports/DB opens."""
from pathlib import Path
import os,stat,hashlib,json,zipfile,base64,shutil
S=Path('/dev/shm/product30-checkpoint');B=Path('/dev/shm/github-product30-admission')
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def save(n,v):
 p=B/n;assert not p.exists(),str(p);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def meta(p):
 s=p.lstat();v={'source':str(p),'mode':stat.S_IMODE(s.st_mode),'inode':s.st_ino,'device':s.st_dev,'mtime_ns':s.st_mtime_ns}
 if stat.S_ISDIR(s.st_mode):return dict(v,kind='dir',file_type=stat.S_IFDIR)
 if stat.S_ISLNK(s.st_mode):
  t=os.readlink(p);b=os.fsencode(t);return dict(v,kind='symlink',file_type=stat.S_IFLNK,symlink_target=t,bytes=len(b),sha256=sha(b))
 assert stat.S_ISREG(s.st_mode),str(p)
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return dict(v,kind='file',file_type=stat.S_IFREG,bytes=s.st_size,sha256=h.hexdigest())
def catalog():
 rows={}
 for p in [S]+sorted(S.rglob('*')):
  v=meta(p);r=str(p.relative_to(S));n='sealed-packet'+('/' if r=='.' else '/'+r);n+=('/' if v['kind']=='dir' and not n.endswith('/') else '');rows[n]=v
 return rows
def makezip(name,rows):
 p=B/name
 with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,v in sorted(rows.items()):
   i=zipfile.ZipInfo(n,(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(v['file_type']|v['mode'])<<16;i.compress_type=zipfile.ZIP_DEFLATED
   if v['kind']=='dir':z.writestr(i,b'');continue
   if v['kind']=='symlink':b=os.fsencode(os.readlink(v['source']));assert sha(b)==v['sha256'];z.writestr(i,b);continue
   h=hashlib.sha256();count=0
   with Path(v['source']).open('rb') as f,z.open(i,'w') as out:
    for b in iter(lambda:f.read(1024*1024),b''):out.write(b);h.update(b);count+=len(b)
   assert count==v['bytes'] and h.hexdigest()==v['sha256'],n
  i=zipfile.ZipInfo('CHECKPOINT-MANIFEST.json',(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|0o600)<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,(json.dumps(rows,indent=2,sort_keys=True)+'\n').encode())
 return p
def provider(key,path):
 before=meta(path);members=[]
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  for i in z.infolist():
   b=z.read(i);typ=stat.S_IFMT(i.external_attr>>16);assert typ in (stat.S_IFREG,stat.S_IFDIR,stat.S_IFLNK) or (typ==0 and i.filename=='CAPTURE-MANIFEST.json');members.append({'path':i.filename,'bytes':len(b),'sha256':sha(b),'mode':stat.S_IMODE(i.external_attr>>16),'file_type':typ,'dir':i.is_dir(),'symlink_target':os.fsdecode(b) if typ==stat.S_IFLNK else None})
 d=B/(key+'-parts');d.mkdir();parts=[];off=0
 with path.open('rb') as f:
  for idx,b in enumerate(iter(lambda:f.read(500000),b'')):
   a=base64.b64encode(b);n=f'{key}-parts/part-{idx:03}.base64';(B/n).write_bytes(a);parts.append({'path':n,'offset':off,'bytes':len(b),'sha256':sha(b),'raw_git_sha1':git(b),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)});off+=len(b)
 assert meta(path)==before
 r={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':before['bytes'],'sha256':before['sha256'],'zip_entries':len(members),'members':members,'parts':parts,'scope':'Installed product30/native18 admission-only candidate IN_PROGRESS. Product29 failure preserved; no fullF3/fullrelease/human qualification. Current28 bounded predecessor unchanged.'};save(key+'-recipe.json',r);return r

B.mkdir()
assert sha((S/'MANIFEST.json').read_bytes())=='0842ec71cefe10ab70731e73b83df6f6678fd08619b51a988ac675343e8a8c62'
assert sha((S/'BUILD_STATUS.json').read_bytes())=='da8510c3075f2adcf13f50e05adef530f95efb930a7d1536fd3619c12fef3f31'
manifest=json.loads((S/'MANIFEST.json').read_bytes());allfiles={str(p.relative_to(S)) for p in S.rglob('*') if p.is_file()}
assert len(manifest)==159 and allfiles==set(manifest)|{'MANIFEST.json'}
for n,v in manifest.items():
 m=meta(S/n);assert all(m[k]==v[k] for k in ('bytes','sha256')),n
before=catalog();save('source-before.json',before)
critical={n:v for n,v in before.items() if Path(v['source']).name!='Product29_30_Actual_Admission_Raw.zip'}
cp=makezip('Product30_Admission_Critical_IN_PROGRESS.zip',critical);cr=provider('critical',cp)
bp=makezip('Product30_Admission_Complete_Packet_IN_PROGRESS.zip',before);br=provider('body',bp)
rp=S/'Product29_30_Actual_Admission_Raw.zip';assert rp.stat().st_size==6705819 and sha(rp.read_bytes())=='791434d813efd8596bdd8498a6459d37fcf43847c30a568d7437c01540246d75'
rr=provider('raw',rp)
after=catalog();assert before==after;save('source-after.json',after)
context={'status':'BOUNDED_INSTALLED_EXHIBITION_ADMISSION_ONLY_IN_PROGRESS','packet':str(S),'manifest_sha256':'0842ec71cefe10ab70731e73b83df6f6678fd08619b51a988ac675343e8a8c62','ledger_sha256':'da8510c3075f2adcf13f50e05adef530f95efb930a7d1536fd3619c12fef3f31','manifest_files':159,'physical_files':160,'runtime_sha256':'436ccf17e0be08159ac31dca14025958d1c9a407183eb2ff8ebe98df189bdd2b','product_wheel_sha256':'8562fa30d8f64fdcf61f1d5f646db7512b1911549f8a68af00f8371763294d17','native18_wheel_sha256':'d2d6cbec7b404a451c13d20a61d1640bb7e2b639ae970f8f254b49a46c895626','source_trees':{'product30/package':41,'product29-antecedent/package':41},'actual_evidence':'Installed30 ordinaryClientprepare/preview/activate/exact replay/reopen;3player negative controls; nativeverify/registry/FK/checkedbackup;242 matched source/wheel/install payloads. Evidence retained, not rerun by writer.','repair':'Compiler optional audience default mutation in29 caused real raw-reload mismatch DEPENDENCY;30 removes only mutating default, strict native/history guards unchanged. Original failure and two diagnostic copies preserved; exact regression RED/GREEN and20sourcepure methods retained.','source_only':'Offer repair17pure and Media28harness21pure; neither integrated/runtime world proof.','limits':['admission only, no opposedcontest/consent/award/repair/fullF3','no human/allF1-F5/fullrelease/generalhost claim','Current28 bounded predecessor untouched','Later31 work excluded','full469MB historical continuation not this compact packet; portable reconstruction active independently, Library15 latest at freeze'],'raw_capture':'Existing4actualOwnerlocks sourcebeforeafterCRC/SHA/modes; this writer only reads frozen packet/ZIP, opens no DB/native/client. Not all negative worlds healthy. CAPTURE-MANIFEST actual file_type0 retained exactly.','native_source_anchor':{'SAM':'78f68bde6496a3598d9059bf0e052b51ec494ca7','Kage':'1598555d04c3846a6ba4208b4b35dc701515474b','checkpoint':'F3A-NATIVE18-20261022-IN_PROGRESS','source_files':745},'providers':{k:{x:r[x] for x in ('filename','bytes','sha256','zip_entries')} for k,r in [('critical',cr),('body',br),('raw',rr)]},'source_before_after_metadata_exact':True,'writer_execution':'byte packaging only; no DB/Engine/Client/build/test/source/Library/automation/native/process probes'}
save('context.json',context)
shutil.copy2('/dev/shm/github-product29-admission/reconstruct.py',B/'reconstruct.py')
selected=['BUILD_STATUS.json','MANIFEST.json','CONTINUE.md','NATIVE_DEPENDENCY.json','RAW_CAPTURE.json','REPORT.json','native18-canonical-source-manifest.json','product30/FIX.json','product30/identity-lock.json','product30/HARNESS_SHAPE_CORRECTION.json','product30/command-preservation-source-green.log','product30/compiler-source-20.log','product29-antecedent/command-preservation-red.log']
direct=[{'path':n,'local':str(B/n)} for n in ['context.json','critical-recipe.json','reconstruct.py']]+[{'path':'selected/'+n,'local':str(S/n)} for n in selected]+[{'path':'admission30-package/'+str(p.relative_to(S/'product30/package')),'local':str(p)} for p in sorted((S/'product30/package').rglob('*')) if p.is_file()]
assert len([x for x in direct if x['path'].startswith('admission30-package/')])==41
(B/'upload-text').mkdir()
def plan(items,key):
 for idx,x in enumerate(items):
  b=Path(x['local']).read_bytes();t=B/'upload-text'/f'{key}-{idx:03}.base64';t.write_bytes(base64.b64encode(b));x.update(bytes=len(b),sha256=sha(b),git_sha1=git(b),encoding='base64',transport=str(t),transport_bytes=t.stat().st_size)
 return items
direct=plan(direct,'critical')
for x in cr['parts']:direct.append({'path':x['path'],'local':str(B/x['path']),'transport':str(B/x['path']),'transport_bytes':x['ASCII_bytes'],'bytes':x['ASCII_bytes'],'sha256':x['ASCII_sha256'],'git_sha1':x['git_sha1'],'encoding':'utf-8'})
save('critical-upload-plan.json',direct)
body=plan([{'path':n,'local':str(B/n)} for n in ['body-recipe.json','raw-recipe.json','source-before.json','source-after.json']],'body')
for r in [br,rr]:
 for x in r['parts']:body.append({'path':x['path'],'local':str(B/x['path']),'transport':str(B/x['path']),'transport_bytes':x['ASCII_bytes'],'bytes':x['ASCII_bytes'],'sha256':x['ASCII_sha256'],'git_sha1':x['git_sha1'],'encoding':'utf-8'})
save('body-upload-plan.json',body)
save('capture-result.json',dict(manifest_files=159,physical_files=160,bytes=sum((S/n).stat().st_size for n in allfiles),providers=context['providers'],source_before_after_metadata_exact=True,DB_opened=False))
print(json.dumps({'providers':context['providers'],'critical_uploads':len(direct),'body_uploads':len(body)},indent=2))

