"""Frozen-packet byte packaging only; no candidate or native imports/DB opens."""
from pathlib import Path
import os,stat,hashlib,json,zipfile,base64,shutil
S=Path('/dev/shm/continuation-current28-reconstruction/PORTABLE-KIT');B=Path('/dev/shm/github-current28-reconstruction-kit')
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
  v=meta(p);r=str(p.relative_to(S));n='frozen-kit'+('/' if r=='.' else '/'+r);n+=('/' if v['kind']=='dir' and not n.endswith('/') else '');rows[n]=v
 rows['PORTABLE-KIT-RECEIPT.json']=meta(S.parent/'PORTABLE-KIT-RECEIPT.json')
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
 r={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':before['bytes'],'sha256':before['sha256'],'zip_entries':len(members),'members':members,'parts':parts,'scope':'Exact historical current28/native16 fullcontinuation recovery KIT, not fulltargetbody; external14providers required inclLibrary15, current30/31/32 excluded, no fullrelease or Libraryversion.'};save(key+'-recipe.json',r);return r


manifest=json.loads((S/'frozen-manifest.json').read_bytes())
assert sha((S/'frozen-manifest.json').read_bytes())=='aa02af7ade3e8d4a3c28af8833f70453ab08d3ff87e17ff40e3de2ff8ffaf58a'
files={x['path']:x for x in manifest['files']};allfiles={str(p.relative_to(S)) for p in S.rglob('*') if p.is_file()}
assert len(files)==64 and allfiles==set(files)|{'frozen-manifest.json'}
for n,v in files.items():
 m=meta(S/n);assert all(m[k]==v[k] for k in ['bytes','sha256','mode']),n
assert sum((S/n).stat().st_size for n in allfiles)==10430657
before=catalog();save('source-before.json',before)
with zipfile.ZipFile(S/'continuation-delta.zip') as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==155
 dm=[]
 for i in z.infolist():
  b=z.read(i);dm.append(dict(path=i.filename,bytes=len(b),sha256=sha(b),mode=stat.S_IMODE(i.external_attr>>16),file_type=stat.S_IFMT(i.external_attr>>16),dir=i.is_dir()))
save('delta-member-proof.json',dm)
ids=json.loads((S/'provider-identities.json').read_bytes());assert len(ids['providers'])==14
anchors=[]
for p in ids['providers']:
 if p['id']=='library-v15':continue
 x=p['recipe_bootstrap'];d=(S/x['delta_member']).read_bytes()
 assert len(d)==x['bytes'] and sha(d)==x['sha256'] and git(d)==x['computed_git_blob_sha1'],p['id']
 anchors.append(dict(provider=p['id'],retrieval=p['retrieval'],bootstrap=x))
assert len(anchors)==13;save('anchor-plan.json',anchors)
kp=makezip('Current28_Full_Continuation_Portable_Kit_IN_PROGRESS.zip',before);kr=provider('kit',kp)
after=catalog();assert before==after;save('source-after.json',after)
context={'status':'EXACT_HISTORICAL_CURRENT28_FULL_CONTINUATION_RECOVERY_KIT_REMOTE_CUSTODY_IN_PROGRESS','frozen_kit':str(S),'frozen_manifest_sha256':'aa02af7ade3e8d4a3c28af8833f70453ab08d3ff87e17ff40e3de2ff8ffaf58a','payload_files':64,'physical_files_including_manifest':65,'physical_file_bytes':10430657,'external_root_receipt':'PORTABLE-KIT-RECEIPT.json','carrier_source_files_including_external_receipt':66,'target':ids['target'],'providers':14,'canonical_bootstrap_recipes':13,'recursive_inputs':'All14complete rawproviders required,771515617B total. Library15 pinnedexternalinput remains required; Gitimmutableanchors+recursivecurrent26basechain retained. No suppliedoriginalrawdup or guessedhostpaths.','delta':{'bytes':6563350,'sha256':'72d043789401811d93eb4191affd2585576eb0f1d1405e2a4c58aded4e440d2a','members':155},'recipe_sha256':'fd8587de1001c1a132e3a7adee8d10ffa2df36abca4dad605e45173c8644778c','helper_sha256':'5db3d4d1bb40ddf95ebc5da2fb2e4129c921b1d82440bbf817ec99c69def3b27','wrapper_sha256':'6222ff063eaffbb939ff8da926cf4ebd97ee35ca7729d88d035726e733c9a87f','actual_historical_evidence':'Exact469620062B/b13c9619efc76e5d5f311755906df65e73c7b2ea9417cee50594b37007b54b04 fullreconstruction PASS plus independent all12688entry readback; all14providerSHA after exact. Newderivedduplicate hardlinknames released onlyafter retainedoriginal+readback proof. Receipts frozenhistorical; writer does not rerun full469MBreconstruction.','independent_readback_receipt_sha256':'3ab8dc6ef3adb21fac2c5140f0ca87e6c429752c50c7cb2d153abfa66f517a30','scope':'Complete historicalcurrent28/native16 snapshot, allLibrary15parentbytes/history preserved; native18 futurediagnosticevidence only. Current30/31/32 NOTinside; no fullrelease/allF1-F5/Librarynewversion.','provider':{k:kr[k] for k in ['filename','bytes','sha256','zip_entries']},'source_before_after_metadata_exact':True,'writer_execution':'Bytepackaging/read-onlyGitanchor verification only; no DB/Engine/Client/native/processprobe/test/build/world/source/Library/automation effects; nochildren'}
save('context.json',context)
shutil.copy2('/dev/shm/github-product31-offers/reconstruct.py',B/'reconstruct.py')
for n in ['verify_readback.py','check_tree_hash.py']:
 t=(Path('/dev/shm/github-product31-offers')/n).read_text().replace('/dev/shm/github-product31-offers','/dev/shm/github-current28-reconstruction-kit');(B/n).write_text(t)
direct=[dict(path='kit/'+n,local=str(S/n)) for n in sorted(allfiles) if n!='continuation-delta.zip']+[dict(path='PORTABLE-KIT-RECEIPT.json',local=str(S.parent/'PORTABLE-KIT-RECEIPT.json'))]+[dict(path=n,local=str(B/n)) for n in ['context.json','kit-recipe.json','reconstruct.py']]
(B/'upload-text').mkdir()
def plan(items,key):
 for idx,x in enumerate(items):
  b=Path(x['local']).read_bytes();t=B/'upload-text'/f'{key}-{idx:03}.base64';t.write_bytes(base64.b64encode(b));x.update(bytes=len(b),sha256=sha(b),git_sha1=git(b),encoding='base64',transport=str(t),transport_bytes=t.stat().st_size)
 return items
direct=plan(direct,'kit')
for x in kr['parts']:direct.append(dict(path=x['path'],local=str(B/x['path']),transport=str(B/x['path']),transport_bytes=x['ASCII_bytes'],bytes=x['ASCII_bytes'],sha256=x['ASCII_sha256'],git_sha1=x['git_sha1'],encoding='utf-8'))
save('upload-plan.json',direct);save('capture-result.json',dict(kit_physical_files=65,external_receipt=1,source_before_after_metadata_exact=True,provider=context['provider'],delta_CRC155memberproof=True,DB_opened=False))
print(json.dumps({'provider':context['provider'],'SAM_payloads':len(direct),'mirrored_direct_metadata':len(direct)-len(kr['parts']),'parts':len(kr['parts']),'source_metadata_unchanged':True},indent=2))

