"""Frozen-packet byte packaging only; no candidate or native imports/DB opens."""
from pathlib import Path
import os,stat,hashlib,json,zipfile,base64,shutil
S=Path('/dev/shm/product29-admission-repaired');B=Path('/dev/shm/github-product29-admission')
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
 for n in ['freeze_product29_admission_initial_path_expression.py','product29-admission-freeze.log','freeze_product29_admission.py','freeze_product29_admission_r2.py','product29-admission-freeze-r2.log']:
  p=Path('/dev/shm')/n;rows['additive-freeze-context/'+n]=meta(p)
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
   b=z.read(i);typ=stat.S_IFMT(i.external_attr>>16);assert typ in (stat.S_IFREG,stat.S_IFDIR,stat.S_IFLNK);members.append({'path':i.filename,'bytes':len(b),'sha256':sha(b),'mode':stat.S_IMODE(i.external_attr>>16),'file_type':typ,'dir':i.is_dir(),'symlink_target':os.fsdecode(b) if typ==stat.S_IFLNK else None})
 d=B/(key+'-parts');d.mkdir();parts=[];off=0
 with path.open('rb') as f:
  for idx,b in enumerate(iter(lambda:f.read(500000),b'')):
   a=base64.b64encode(b);n=f'{key}-parts/part-{idx:03}.base64';(B/n).write_bytes(a);parts.append({'path':n,'offset':off,'bytes':len(b),'sha256':sha(b),'raw_git_sha1':git(b),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)});off+=len(b)
 assert meta(path)==before
 r={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':before['bytes'],'sha256':before['sha256'],'zip_entries':len(members),'members':members,'parts':parts,'scope':'Compact future product29 source-only packet; current28/native16 authority unchanged. No product29 build/install/full historical continuation or full-release qualification.'};save(key+'-recipe.json',r);return r
assert sha((S/'MANIFEST.json').read_bytes())=='ec4335a99d3f5bab2f31b0024a904c965bbc9b5911a14ef4db07636d2a586127'
assert sha((S/'BUILD_STATUS.json').read_bytes())=='70577641acf0f46bb0d78dace6cce4039598ad2bdb3e1b60f3d12d7c11507a09'
manifest=json.loads((S/'MANIFEST.json').read_bytes())['files'];allfiles={str(p.relative_to(S)) for p in S.rglob('*') if p.is_file()};assert len(manifest)==224 and allfiles==set(manifest)|{'MANIFEST.json'}
for n,v in manifest.items():
 p=S/n;m=meta(p);assert all(m[k]==v[k] for k in ('bytes','sha256','mode')),n
before=catalog();save('source-before.json',before)
critical={n:v for n,v in before.items() if v['kind']!='dir' and '.sqlite' not in Path(v['source']).name and not Path(v['source']).name.endswith('.bak')}
cp=makezip('Product29_Admission_Source_Critical_IN_PROGRESS.zip',critical);cr=provider('critical',cp)
bp=makezip('Product29_Admission_Complete_Compact_Packet_IN_PROGRESS.zip',before);br=provider('body',bp)
after=catalog();assert before==after;save('source-after.json',after)
context={'status':'SOURCE_ONLY_ADMISSION_HISTORY_REPAIRED_IN_PROGRESS','current_authority':'Current product28/native16 untouched','future_candidate':'Product29 targets native18, not versionbumped/built/installed/adopted; current version/lock bytes retained intentionally','packet_source':str(S),'sealed_manifest':{'sha256':'ec4335a99d3f5bab2f31b0024a904c965bbc9b5911a14ef4db07636d2a586127','manifest_files':224,'physical_files_including_manifest':225},'authoritative_ledger':{'checkpoint_path':'selected/BUILD_STATUS.json','sha256':'70577641acf0f46bb0d78dace6cce4039598ad2bdb3e1b60f3d12d7c11507a09','workspace_ec426_precursor':'historical only, no competing current claim'},'production_source_entries':40,'source_entries_including_authored_test':41,'compiler_sha256':'550b5db49685571d15e225883c367a4884665d12b539b1cf47b7c9c461eb2eb9','reported_component_checks':'Actual20pure compiler PASS with rootcommon; same11source/native18-installed-history checks rerun, not22distinct','failure_and_repair':'IndependentP2wholeworldslot preflight gap and actualrootinvalid r1 acceptance preserved. R2 reuses ONE originalD6four-index loop, conflictrefusal and validdistinctproposal both zeroWrites. Nativeguard unchanged.','historical_notes':'InitialD6AST body-reuse syntax receipt and shared-uniqueness-repair.json UNEXECUTED author note remain historical; actualr2results supplement. No one clean original fullsuite claim.','actual_closed_world_directories':[str(p.relative_to(S)) for p in sorted(S.rglob('closed-world'))],'raw_worlds_universally_healthy':False,'packet_not_complete_historical_continuation':True,'native18_paired_dependency':['78f68bde6496a3598d9059bf0e052b51ec494ca7','1598555d04c3846a6ba4208b4b35dc701515474b'],'Library_at_freeze':'CompleteProduct28-only891MB historical continuation62a916... all7308parent conservation/gates passed; actual512MiB536870912 cap. Flat ZIP_LZMA469620062-byte measurement fits with12688entries; new output/save pending at this packet freeze. Future29 excluded. No Library mutation by this writer.','additive_freeze_context':'InitialTypeError path expression beforeeffects and exact firsthelper/log plus correctedtool/r2log captured outside sealed tree','providers':{k:{x:r[x] for x in ('filename','bytes','sha256','zip_entries')} for k,r in [('critical',cr),('body',br)]},'body_remote_custody':'Pending until full body actual readback receipt','source_before_after_all_metadata_exact':True,'no_DB_native_test_build_source_automation_Library_effects':True,'full_product_F1_F5_F3_world_season_human_generalhost_qualification':False};save('context.json',context)
shutil.copy2('/workspace/scratch/5c7ed9200168/recovery-20261022/github-native18-future/reconstruct.py',B/'reconstruct.py')
# Direct future source and exact small reports in both repositories.
selected=['BUILD_STATUS.json','MANIFEST.json','CURRENT_LEDGER_LOCATION.json','IN_PROGRESS.json','REPORT.md','BASELINE.json','shared-uniqueness-repair.json','source-syntax-and-original-methods.json','root-source-copy-proof.json','root-compiler20-repaired.log','admission-history-r2.log','conflict-r1/closed-world/result.json','conflict-r2/closed-world/result.json','independent-review-r1/REPORT.md']
selected=[n for n in selected if (S/n).exists()]
sources=list(json.loads((S/'IN_PROGRESS.json').read_bytes())['source_files'])
direct=[{'path':n,'local':str(B/n)} for n in ['context.json','critical-recipe.json','reconstruct.py']]+[{'path':'selected/'+n,'local':str(S/n)} for n in selected]+[{'path':'future-package/'+n,'local':str(S/'package'/n)} for n in sources]
(B/'upload-text').mkdir()
for idx,x in enumerate(direct):
 b=Path(x['local']).read_bytes();t=B/'upload-text'/f'critical-{idx:03}.base64';t.write_bytes(base64.b64encode(b));x.update(bytes=len(b),sha256=sha(b),git_sha1=git(b),encoding='base64',transport=str(t),transport_bytes=t.stat().st_size)
for x in cr['parts']:direct.append({'path':x['path'],'local':str(B/x['path']),'transport':str(B/x['path']),'transport_bytes':x['ASCII_bytes'],'bytes':x['ASCII_bytes'],'sha256':x['ASCII_sha256'],'git_sha1':x['git_sha1'],'encoding':'utf-8'})
save('critical-upload-plan.json',direct)
save('capture-result.json',{'packet_manifest_files':224,'packet_physical_files':225,'all_file_bytes':sum((S/n).stat().st_size for n in allfiles),'world_directories':context['actual_closed_world_directories'],'source_before_after_metadata_exact':True,'ZIP_providers':context['providers'],'native_DB_opened':False})
print(json.dumps({'critical':context['providers']['critical'],'critical_parts':len(cr['parts']),'critical_uploads':len(direct),'body':context['providers']['body'],'body_parts':len(br['parts']),'sealed225files_unchanged':True,'raw_world_directories':len(context['actual_closed_world_directories'])},indent=2),flush=True)
