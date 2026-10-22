"""Frozen-packet byte packaging only; no candidate or native imports/DB opens."""
from pathlib import Path
import os,stat,hashlib,json,zipfile,base64,shutil
S=Path('/dev/shm/product31-checkpoint');B=Path('/dev/shm/github-product31-offers')
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
 r={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':before['bytes'],'sha256':before['sha256'],'zip_entries':len(members),'members':members,'parts':parts,'scope':'Installed product31/native18 bounded unreserved offers/scripted own consent plus independent AI later-use recipient and relocation IN_PROGRESS. No actual contestplay/award/helperrepair/fullF3/human/fullrelease. Prior candidates preserved.'};save(key+'-recipe.json',r);return r

assert sha((S/'MANIFEST.json').read_bytes())=='c06a476d55c9252e70bcf7d539a8a1773b8c84b0600ded623584b46f6d048317'
assert sha((S/'BUILD_STATUS.json').read_bytes())=='b3a826c6cf36726362c8f7064968e5dff09de9790c4101007b0a7fd84b08d7a0'
manifest=json.loads((S/'MANIFEST.json').read_bytes());allfiles={str(p.relative_to(S)) for p in S.rglob('*') if p.is_file()}
assert len(manifest)==105 and allfiles==set(manifest)|{'MANIFEST.json'}
for n,v in manifest.items():
 m=meta(S/n);assert all(m[k]==v[k] for k in ('bytes','sha256')),n
pre=json.loads((B/'readonly-freeze-catalog.json').read_bytes())
for p in [S,*sorted(S.rglob('*'))]:
 v=meta(p);old=pre[str(p.relative_to(S))];assert all(v[k]==a for k,a in old.items()),str(p)
before=catalog();save('source-before.json',before)
critical={n:v for n,v in before.items() if Path(v['source']).name!='Product31_Offers_Recipient_Relocation_Raw.zip'}
cp=makezip('Product31_Offers_Critical_IN_PROGRESS.zip',critical);cr=provider('critical',cp)
bp=makezip('Product31_Offers_Complete_Packet_IN_PROGRESS.zip',before);br=provider('body',bp)
rp=S/'Product31_Offers_Recipient_Relocation_Raw.zip';assert rp.stat().st_size==2522263 and sha(rp.read_bytes())=='cca2d1e2a0cbd2ea5355308341efe73bc335b0049b82ee4b173be8955bc91eba'
rr=provider('raw',rp)
after=catalog();assert before==after;save('source-after.json',after)
context={'status':'BOUNDED_INSTALLED_UNRESERVED_OFFERS_OWN_CONSENT_AI_RECIPIENT_RELOCATION_ONLY_IN_PROGRESS','packet':str(S),'manifest_sha256':'c06a476d55c9252e70bcf7d539a8a1773b8c84b0600ded623584b46f6d048317','ledger_sha256':'b3a826c6cf36726362c8f7064968e5dff09de9790c4101007b0a7fd84b08d7a0','manifest_files':105,'physical_files':106,'runtime_sha256':'3cc6f3390a636b3e95d8520186d1994f1ba1440ed165dc2293b75fc34f6f29d3','product_wheel_sha256':'a17dac8ed4172b2cda1ccf50e0fd09f67d9f4b7ebd64a34ed81c26616c0fa1f4','native18_wheel_sha256':'d2d6cbec7b404a451c13d20a61d1640bb7e2b639ae970f8f254b49a46c895626','source_entries':42,'production_entries':41,'actual_evidence':'Unreserved operator offers and separately bound SCRIPTED own accepted/declined/withdrawn choices; exact accepted-message replay does not restore withdrawn consent; stale refusal and known/missing privacy. Fresh independent AI recipient read normalterms/currentchoices, changed no consent, authored4495B private assessment through ordinary real_work and retrieved exact acceptedoutput. Actual physicalrelocation+freshactor exactthree reads, nativeverify/directregistry/FK/checkedbackup and243sameprocess source/wheel/installedpayloads retained. Evidence not rerun by writer.','antecedents':'Original raw-kind failure, unrelated withdrawal dependency, cached-replay current-authority gap and exact prerepair sources retained. Source/parser/mock checks are bounded, not wholeworld qualification.','limits':['no actual contestplay/opposed choices/winner/award/helperrepair/season/fullF3','scripted own choices are not independent AI entrant choices/human agreement; recipient made no consent changes','no human/mastery/canon/allF1-F5/fullrelease/generalhost claim','prior28/current26 evidence remains exact-version-bound','source32 and reconstructionKIT excluded pending separate frozen commission','small compact checkpoint is not completehistoricalcontinuation or Librarysave; frozen CONTINUE pendingreconstruction note retained as historical freeze context'],'raw_capture':'Existing1actualOwnerlock capture,137sourceentries+CAPTUREmanifest138ZIPmembers, onecomplete movedworld. SourcebeforeafterCRC/SHA/modes. Thiswriter reads frozenpacket/ZIP only, opensnoDB/native/client. Original CAPTURE-MANIFEST actualtype0 preserved.','native_source_anchor':{'SAM':'78f68bde6496a3598d9059bf0e052b51ec494ca7','Kage':'1598555d04c3846a6ba4208b4b35dc701515474b','checkpoint':'F3A-NATIVE18-20261022-IN_PROGRESS','source_files':745},'providers':{k:{x:r[x] for x in ('filename','bytes','sha256','zip_entries')} for k,r in [('critical',cr),('body',br),('raw',rr)]},'source_before_after_metadata_exact':True,'readonly_preflight_catalog_still_exact':True,'writer_execution':'byte packaging only; no DB/Engine/Client/build/test/source/Library/automation/native/processprobes; no children'}
save('context.json',context)
shutil.copy2('/dev/shm/github-product30-admission/reconstruct.py',B/'reconstruct.py')
for n in ['verify_readback.py','check_tree_hash.py']:
 t=(Path('/dev/shm/github-product30-admission')/n).read_text().replace('/dev/shm/github-product30-admission','/dev/shm/github-product31-offers');(B/n).write_text(t)
selected=['BUILD_STATUS.json','MANIFEST.json','CONTINUE.md','RAW_CAPTURE.json','REPORT.json','SOURCE_MANIFEST.json','STATUS.json','WIRE_INSTALLED_RESULT.json','WIRE_PURE_RESULT.json','identity-lock.json','native18-canonical-source-manifest.json','native18-paired-dependency-receipt.json','product30-antecedent-paired-receipt.json']
direct=[{'path':n,'local':str(B/n)} for n in ['context.json','critical-recipe.json','reconstruct.py']]+[{'path':'selected/'+n,'local':str(S/n)} for n in selected]+[{'path':'offers31-package/'+str(p.relative_to(S/'package')),'local':str(p)} for p in sorted((S/'package').rglob('*')) if p.is_file()]
assert len([x for x in direct if x['path'].startswith('offers31-package/')])==42
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
save('capture-result.json',dict(manifest_files=105,physical_files=106,bytes=sum((S/n).stat().st_size for n in allfiles),providers=context['providers'],source_before_after_metadata_exact=True,DB_opened=False))
print(json.dumps({'providers':context['providers'],'critical_uploads':len(direct),'body_uploads':len(body)},indent=2))


