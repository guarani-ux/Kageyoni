from pathlib import Path
import json,hashlib,stat,zipfile,base64,os,shutil
R=Path('/workspace/scratch/5c7ed9200168/recovery-20261022');B=R/'github-native18-future'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def meta(p):
 s=p.lstat();assert stat.S_ISREG(s.st_mode)
 b=p.read_bytes();return {'bytes':len(b),'sha256':sha(b),'mode':stat.S_IMODE(s.st_mode),'type':'file'}
def provider(key,path):
 raw=path.read_bytes();members=[]
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  for i in z.infolist():
   b=z.read(i);typ=stat.S_IFMT(i.external_attr>>16)
   members.append({'path':i.filename,'bytes':len(b),'sha256':sha(b),'mode':stat.S_IMODE(i.external_attr>>16),'file_type':typ,'dir':i.is_dir(),'symlink_target':b.decode() if typ==stat.S_IFLNK else None})
 parts=[];d=B/(key+'-parts');d.mkdir()
 for idx,off in enumerate(range(0,len(raw),500000)):
  b=raw[off:off+500000];a=base64.b64encode(b);name=f'{key}-parts/part-{idx:03}.base64';(B/name).write_bytes(a)
  parts.append({'path':name,'offset':off,'bytes':len(b),'sha256':sha(b),'raw_git_sha1':git(b),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)})
 recipe={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':len(raw),'sha256':sha(raw),'zip_entries':len(members),'members':members,'parts':parts,'scope':'Future native18 implementation evidence only; current product28/native16 remains authority; all full release/F1-F5 false.'}
 save(B/(key+'-recipe.json'),recipe);return recipe
rows={}; originals={}
def add(p,n=None):
 if n is None:n=str(p.relative_to(R))
 if n in rows:
  assert meta(p)=={k:rows[n][k] for k in ('bytes','sha256','mode','type')}
  return
 assert n not in rows;npath=B/'snapshot'/n;npath.parent.mkdir(parents=True,exist_ok=True);before=meta(p);b=p.read_bytes();assert sha(b)==before['sha256'];npath.write_bytes(b);os.chmod(npath,before['mode']);assert meta(p)==before==meta(npath)
 rows[n]={'source':str(p),'snapshot':str(npath),**before};originals[str(p)]=before
ledger=R/'BUILD_STATUS-before-native18-count-clarification.json';assert sha(ledger.read_bytes())=='fe6fde09c143bb4cc654a8b0a3d5d7416216e62e8cf159f972585581f089fb12';add(ledger,'BUILD_STATUS-frozen-fe6fde09.json')
add(R/'BUILD_STATUS.json','BUILD_STATUS-after-count-clarification.json')
for ver,root,mfile in [('18','f3a-root-integration-r2','final-canonical-source-manifest.json'),('17','f3a-root-integration','integrated-source-manifest.json')]:
 manifest=json.loads((R/root/mfile).read_bytes());assert ver!='18' or len(manifest)==745
 add(R/root/mfile)
 for n,v in sorted(manifest.items()):
  p=R/root/'engine'/n;h=v['sha256'] if isinstance(v,dict) else v
  assert sha(p.read_bytes())==h,n
  if isinstance(v,dict):assert p.stat().st_size==v['bytes']
  add(p)
 for p in (R/root/'distributions').glob('*.whl'):add(p)
 for p in sorted((R/root).iterdir()):
  if p.is_file() and p.suffix in ('.json','.py','.log','.patch'):add(p)
 for sub in ('installed-r1','review-negative-r1','fork-boundary-r1','fork-boundary-r2'):
  d=R/root/sub
  if d.exists():
   for p in sorted(d.rglob('*')):
    if p.is_file() and p.suffix in ('.json','.xml','.log','.txt','.py'):add(p)
# Source review, original leaf and current proposal history remain distinct.
for n in ['F3a-native-root-contract.md','native18-final-freeze-context.json'] :add(R/n)
for root in ['f3a-native-r2','f3a-common-independent-review','f3a-product-grounding']:
 for p in sorted((R/root).rglob('*')):
  if p.is_file() and ('engine' not in p.relative_to(R/root).parts):add(p)
for n in ['f3a-native-r2/engine/kageyoni/contests.py','f3a-native-r2/engine/migration_035.sql','f3a-root-integration-r2/real-copy-maintenance/result.json','f3a-root-integration-r2/real-copy-maintenance/predecessor.json','product28-custody-control-proposal/control_probe.py','product28-custody-control-proposal/config.json','product28-custody-control-proposal/README.md','product28-custody-control-proposal/execution-report.md','product28-custody-control-proposal/execution/stopped-result.json','product28-custody-control-proposal/execution/final-owned-inventory.json','product28-custody-control-proposal/execution/installed-before.json','product28-custody-control-proposal/execution/installed-after-stopped.json']:add(R/n)
assert sha((R/'f3a-root-integration-r2/distributions/kageyoni_engine-11.1.0.dev18-py3-none-any.whl').read_bytes())=='d2d6cbec7b404a451c13d20a61d1640bb7e2b639ae970f8f254b49a46c895626'
save(B/'critical-source-before.json',originals)
path=B/'Future_Native18_Source_Antecedent_Wheels_and_Evidence_IN_PROGRESS.zip'
with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,v in sorted(rows.items()):
  b=Path(v['snapshot']).read_bytes();assert len(b)==v['bytes'] and sha(b)==v['sha256'];i=zipfile.ZipInfo(n,(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|v['mode'])<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,b)
 i=zipfile.ZipInfo('CHECKPOINT-MANIFEST.json',(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|0o600)<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,(json.dumps(rows,indent=2,sort_keys=True)+'\n').encode())
after={p:meta(Path(p)) for p in originals};assert after==originals;save(B/'critical-source-after.json',after);save(B/'selected-source-manifest.json',rows)
r=provider('critical',path)
context={'status':'IN_PROGRESS_FUTURE_NATIVE18_IMPLEMENTATION_EVIDENCE_ONLY','active_product_authority':{'product':'dev28','native':'dev16','runtime':'1289b896d6de9194f286a0e9860e20ff65337b78a3efb536bae981cd90ebc858','native18_adopted_into_product':False},'future_native18':json.loads((R/'f3a-root-integration-r2/bounded-result.json').read_bytes()),'frozen_root_ledger_sha256':'fe6fde09c143bb4cc654a8b0a3d5d7416216e62e8cf159f972585581f089fb12','critical_provider':{k:r[k] for k in ['filename','bytes','sha256','zip_entries']},'native17':'Antecedent37PASS and independent5FAIL1PASS retained; both concrete findings repaired in independent native18 successor; negative worlds not universally healthy.','raw_archive_count_correction':{'native17_source_entries':1467,'native17_ZIP_members':1468,'native18_source_entries':1568,'native18_ZIP_members':1569,'original_archives_and_receipts_unchanged':True},'custody_control':'STOPPED0cases0signals: proc children ENOENT; actual Owner reaped1; worker UNKNOWN; raw41files44140957B; no guard bypass/retry','product_grounding':'27 sources; read-only proposal, no product implementation','body_custody':'Pending complete raw remote providers; no full custody claim until final receipt','qualification':{'product_or_F3_or_world_or_season_or_human_or_general_host':False,'full_F1_F5':False,'prior_failures_erased':False},'effects':'Snapshot/ZIP/Git only; no DB/native/test/build/process execution or source changes.'}
save(B/'context.json',context)
# Small exact sources/reports live under the new checkpoint only, in both repos.
selected=['BUILD_STATUS-frozen-fe6fde09.json','f3a-root-integration-r2/bounded-result.json','f3a-root-integration-r2/final-canonical-source-manifest.json','f3a-root-integration-r2/repair-contract.json','f3a-root-integration-r2/engine/kageyoni/contests.py','f3a-root-integration-r2/engine/kageyoni/engine.py','f3a-root-integration-r2/engine/kageyoni/model.py','f3a-root-integration-r2/engine/kageyoni/persistence/migrations.py','f3a-root-integration-r2/engine/migration_035.sql','f3a-root-integration/installed-r1/attempt-result.json','f3a-root-integration/review-negative-r1/attempt-result.json','f3a-root-integration-r2/installed-r1/attempt-result.json','f3a-root-integration-r2/fork-boundary-r2/result.json','f3a-root-integration-r2/real-copy-maintenance/result.json','f3a-common-independent-review/REPORT.md','product28-custody-control-proposal/execution-report.md','product28-custody-control-proposal/execution/stopped-result.json','f3a-product-grounding/REPORT.md']
direct=[{'path':n,'local':str(B/n)} for n in ['context.json','critical-recipe.json','selected-source-manifest.json']]+[{'path':'selected/'+n,'local':rows[n]['snapshot']} for n in selected]
for d in direct:
 b=Path(d['local']).read_bytes();d.update(bytes=len(b),sha256=sha(b),git_sha1=git(b))
save(B/'direct-stage-files.json',direct)
print(json.dumps({'files':len(rows),'critical':context['critical_provider'],'parts':len(r['parts']),'direct':len(direct),'source_before_after_equal':True},indent=2))
