from pathlib import Path
from contextlib import ExitStack
import json,hashlib,zipfile,stat,base64,shutil,os,fcntl
R=Path('/workspace/scratch/5c7ed9200168/recovery-20261022'); B=R/'github-product28-r3'
def sha(x):return hashlib.sha256(x).hexdigest()
def git(x):return hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest()
def save(n,x):(B/n).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
assert shutil.disk_usage(B).free>1024**3
selected={}
def add(p,n=None):
 p=p.absolute(); assert p.resolve()==p and p.is_file(); raw=p.read_bytes(); n=n or str(p.relative_to(R)); assert n not in selected
 selected[n]={'source':str(p),'bytes':len(raw),'sha256':sha(raw),'mode':stat.S_IMODE(p.stat().st_mode)}
manifest=json.loads((R/'product28-build/final-source-manifest.json').read_bytes())
for n,v in manifest['files'].items():
 p=R/'product28-build/package'/n; x=p.read_bytes();assert len(x)==v['bytes'] and sha(x)==v['sha256'];add(p)
assert len(manifest['files'])==38
for p in sorted((R/'product28-build').iterdir()):
 if p.is_file():add(p)
for p in sorted((R/'product28-build/distributions').iterdir()):add(p)
assert sha((R/'product28-build/distributions/samsara_world-0.5.3.dev28-py3-none-any.whl').read_bytes())=='7360f0b41ed2691abab83bbfaf245eb61215b09f8c4a39fe3ce8a857efff4d4b'
assert sha((R/'product28-build/distributions/kageyoni_engine-11.1.0.dev16-py3-none-any.whl').read_bytes())=='845d7b4aaa3b81c66364eed09d34e91b57e5c0f99df6aaa654b470d4a1db4ff3'
for n in ['prepare_product28_build.py','update_after_product28.py','ledger-product28-update-proof.json','BUILD_STATUS.json','F3a-native-root-contract.md']:add(R/n)
assert selected['BUILD_STATUS.json']['sha256']=='0e68b6f3972c7839383d32d8584053210ad1dfc011ac1b71bb16b4518320d34b'
for root in ['product27-affected-r1','product28-affected-r1','product27-failed-registration-diagnosis','f2f3-grounding']:
 for p in sorted((R/root).rglob('*')):
  if p.is_file():add(p)
for p in sorted((R/'current26/extracted/samsara_core/product/tests').rglob('*.py')):add(p)
for p in sorted((R/'product27-r3-capture').iterdir()):
 if p.is_file() and p.suffix not in ['.zip','.partial']:add(p)
save('selected-source-manifest.json',selected)
def makezip(name, rows):
 p=B/name
 with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,v in sorted(rows.items()):
   raw=Path(v['source']).read_bytes();assert len(raw)==v['bytes'] and sha(raw)==v['sha256'];i=zipfile.ZipInfo(n,date_time=(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|v['mode'])<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,raw)
  z.writestr('CHECKPOINT-MANIFEST.json',(json.dumps(rows,sort_keys=True,indent=2)+'\n').encode())
 return p
capsule=makezip('Product28_Source_Status_IN_PROGRESS.zip',selected)
worlds={};closed=[]
with ExitStack() as stack:
 for label in ['product27-affected-r1','product28-affected-r1']:
  evidence=json.loads((R/label/'readonly-postconditions.json').read_bytes())
  for entry in evidence['worlds']:
   w=Path(entry['world']);fd=os.open(w/'owner.lock',os.O_RDONLY|os.O_NOFOLLOW);stack.callback(os.close,fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);stack.callback(fcntl.flock,fd,fcntl.LOCK_UN);closed.append({'world':str(w),'owner_lock_inode':os.fstat(fd).st_ino,'existing_readonly_exclusive_lock':True})
   actual={}
   for p in sorted(w.rglob('*')):
    assert p.resolve()==p
    if p.is_dir():continue
    assert p.is_file();x=p.read_bytes();rel=str(p.relative_to(w));actual[rel]={'bytes':len(x),'sha256':sha(x)};worlds[label+'/'+w.parent.name+'/'+rel]={'source':str(p),**actual[rel],'mode':stat.S_IMODE(p.stat().st_mode)}
   assert actual==entry['before_manifest'],str(w)
 save('world-source-before.json',worlds);wzip=makezip('Product27_28_Five_Closed_RAM_Worlds_Raw_IN_PROGRESS.zip',worlds)
 after={}
 for n,v in worlds.items():
  p=Path(v['source']);x=p.read_bytes();after[n]={'source':str(p),'bytes':len(x),'sha256':sha(x),'mode':stat.S_IMODE(p.stat().st_mode)}
 assert after==worlds;save('world-source-after.json',after);save('world-capture-result.json',{'closed_worlds':closed,'source_files':len(worlds),'bytes':sum(v['bytes'] for v in worlds.values()),'before_after_equal':True,'prior_readonly_manifests_equal':True,'DB_native_or_process_imports_or_opens':False})
r3=R/'product27-r3-capture/Product27_R3_RAM_OneCase_Raw_Actual.zip';assert r3.stat().st_size==7335302 and sha(r3.read_bytes())=='781ccf5cf6c315e3bb72e9ebe9920201f0c00d33960ce312e39c970fe22877ef'
recipes={}
for key,p in [('source',capsule),('worlds',wzip),('r3',r3)]:
 raw=p.read_bytes();members=[]
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  for i in z.infolist():members.append({'path':i.filename,'bytes':i.file_size,'sha256':sha(z.read(i)),'mode':stat.S_IMODE(i.external_attr>>16),'dir':i.is_dir()})
 if key=='r3':
  assert len(members)==291; cm=json.loads((R/'product27-r3-capture/capture-manifest.json').read_bytes())['members']; assert all(next(x for x in members if x['path']==n)['sha256']==v.get('sha256',sha(b'')) for n,v in cm.items())
 parts=[];(B/(key+'-parts')).mkdir()
 for idx,off in enumerate(range(0,len(raw),500000)):
  x=raw[off:off+500000];a=base64.b64encode(x);n=f'{key}-parts/part-{idx:03}.base64';(B/n).write_bytes(a);parts.append({'path':n,'offset':off,'bytes':len(x),'sha256':sha(x),'raw_git_sha1':git(x),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)})
 rec={'filename':p.name,'bytes':len(raw),'sha256':sha(raw),'zip_entries':len(members),'parts':parts,'members':members,'format':'exact-ASCII500000-raw-provider/1','scope':'IN_PROGRESS byte custody only; all F1-F5 false'};save(key+'-recipe.json',rec);recipes[key]=rec
context={'checkpoint':'PRODUCT28-R3-20261022-IN_PROGRESS','product28_runtime':'1289b896d6de9194f286a0e9860e20ff65337b78a3efb536bae981cd90ebc858','product28_wheel_sha256':'7360f0b41ed2691abab83bbfaf245eb61215b09f8c4a39fe3ce8a857efff4d4b','native16_wheel_sha256':'845d7b4aaa3b81c66364eed09d34e91b57e5c0f99df6aaa654b470d4a1db4ff3','governing_pins':['db9838371a1128124b77fac69677902a4b5820c6','872973f091320f92e3276408090978084928d291'],'expected_parent_pair':['7e6fcf72dc8f6a0673b4796311b806019310f4e8','dbfe76bafe2623711bde1740ddd33cc1390f9d44'],'prior_checkpoint':'core-build/checkpoints/PRODUCT27-MEDIA-20261022-IN_PROGRESS','providers':{k:{a:v[a] for a in ['filename','bytes','sha256','zip_entries']} for k,v in recipes.items()},'limits':['All F1-F5 false; IN_PROGRESS and unqualified.','Product27 original affected run 1 pass, 1 failure, 25 not run.','Product28 original affected run 2 pass, 1 fairness failure, 24 not run. Real wait and poll returned 21; five pure checks passed. Fairness fixture tries an unregistered fake return and is correctly rejected. Original 32 test source files unchanged.','Five closed RAM worlds preserved byte-only under existing owner locks; prior readonly results healthy 2 plus 3.','R3 is ONE healthy product27/native16 RAM owner-loss case with generations1,2 and fresh recipient output; does not erase earlier journal/copied/overlay failures.','Earlier native114 in-process pass coexists with unresolved native journal failure; other82 raw history remains pending custody.','Active f3a-native source and product28-actual-queue-fixture are excluded. No new DB/process/native/build/test execution.']};save('context.json',context)
(B/'CONTINUE.md').write_text('Read context.json and selected/BUILD_STATUS.json. This is an IN_PROGRESS source and raw evidence checkpoint, with three separately reconstructable providers. Preserve every failure and not-run count. R3 belongs to product27, while the current candidate is product28/native16. Do not open included world databases during byte reconstruction. All F1-F5 remain false.\n')
direct=[]
for n in ['context.json','CONTINUE.md','selected-source-manifest.json','source-recipe.json','worlds-recipe.json','r3-recipe.json','world-source-before.json','world-source-after.json','world-capture-result.json']:direct.append({'path':n,'local':str(B/n)})
for n,v in selected.items():
 if not n.startswith('current26/'):direct.append({'path':'selected/'+n,'local':v['source']})
for idx,v in enumerate(direct):
 raw=Path(v['local']).read_bytes();v.update(bytes=len(raw),sha256=sha(raw),git_sha1=git(raw),transport=str(B/'upload-text'/f'{idx}.base64'));Path(v['transport']).parent.mkdir(exist_ok=True);Path(v['transport']).write_bytes(base64.b64encode(raw))
save('direct-stage-files.json',direct)
print(json.dumps({'source_files':len(selected),'world_files':len(worlds),'providers':context['providers'],'part_counts':{k:len(v['parts']) for k,v in recipes.items()},'direct_files':len(direct),'free':shutil.disk_usage(B).free},indent=2))
