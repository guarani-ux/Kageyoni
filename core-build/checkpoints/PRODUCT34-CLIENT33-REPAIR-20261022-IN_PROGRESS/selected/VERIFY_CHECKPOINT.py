"""Compact byte/source/wheel/scope identity ONLY; not full continuation/semantic qualification."""
from pathlib import Path
import hashlib,json,stat,sys,zipfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
load=lambda p:json.loads(Path(p).read_bytes())
m=load(R/'MANIFEST.json');physical={str(p.relative_to(R))for p in R.rglob('*')if p.is_file()and p!=R/'MANIFEST.json'}
assert physical==set(m),(physical-set(m),set(m)-physical)
for n,row in m.items():
 p=R/n;assert p.stat().st_size==row['bytes']and sha(p.read_bytes())==row['sha256']and stat.S_IMODE(p.stat().st_mode)==row['mode'],n
ledger=load(R/'BUILD_STATUS.json');old=load(R/'protected-parent-ledger.json')
for k in('core_loops','old_requirements','old_slices','increments','full_release_increments','full_release_breadth','load_scenarios','resource_policy'):assert ledger[k]==old[k],k
assert set(ledger['full_release_continuation']['stages'])=={'PS1','F1','F2','F3','F4','F5'}and ledger['full_release_qualified']is False and ledger['full_release_continuation']['complete']is False
assert ledger['full_release_continuation']['current_source_identity']is None
s34=load(R/'client34/SOURCE_MANIFEST.json');s33=load(R/'server33-antecedent/SOURCE_MANIFEST.json');assert len(s34)==len(s33)==43
for rel,row in s34.items():assert sha((R/'package'/rel).read_bytes())==row['sha256']
for rel,row in s33.items():
 p=R/'server33-antecedent/package'/rel
 if not p.exists():p=R/'package'/rel
 assert p.stat().st_size==row['bytes']and sha(p.read_bytes())==row['sha256'],rel
native=load(R/'native18-canonical-source-manifest.json');assert len(native)==745
with zipfile.ZipFile(R/'distributions/kageyoni_engine-11.1.0.dev18-py3-none-any.whl')as z:
 assert z.testzip()is None
 native_count=0
 for n in z.namelist():
  if n.endswith('/')or not n.startswith(('kageyoni/','contracts/')):continue
  key=n if n in native else Path(n).name if n.startswith('kageyoni/data/')else n
  row=native[key];b=z.read(n);assert len(b)==row['bytes']and sha(b)==row['sha256'],n;native_count+=1
assert native_count==203
for v,s in((33,s33),(34,s34)):
 i=load(R/('server33-antecedent'if v==33 else'client34')/'identity-lock.json');w=R/'distributions'/('samsara_world-0.5.3.dev'+str(v)+'-py3-none-any.whl');assert sha(w.read_bytes())==i['wheel_sha256']['product']
 with zipfile.ZipFile(w)as z:
  assert z.testzip()is None;n=0
  for name in z.namelist():
   if name.endswith('/')or not name.startswith('samsara/'):continue
   b=z.read(name);assert sha(b)==s[name]['sha256']and len(b)==s[name]['bytes'];n+=1
 assert n+native_count==244
 assert i['wheel_sha256']['engine']=='d2d6cbec7b404a451c13d20a61d1640bb7e2b639ae970f8f254b49a46c895626'
 assert len(i['payloads'])==244
for dep in load(R/'OFFLINE_DEPENDENCIES.json'):
 p=R/'offline-dependencies'/dep['file'];assert p.stat().st_size==dep['bytes']and sha(p.read_bytes())==dep['sha256']
 with zipfile.ZipFile(p)as z:assert z.testzip()is None
assert len(load(R/'OFFLINE_DEPENDENCIES.json'))==20
raw=load(R/'RAW_CAPTURE.json');p=R/'Product33_Complete_Actual_Repair_Failures_Recipient_Raw.zip';assert p.stat().st_size==raw['bytes']and sha(p.read_bytes())==raw['sha256']
with zipfile.ZipFile(p)as z:
 assert z.testzip()is None and len(z.namelist())==len(set(z.namelist()))==raw['ZIP_members'];items=load_json=json.loads(z.read('CAPTURE-MANIFEST.json'));assert len(items)==raw['source_entries']
 for name,row in items.items():
  key=name+'/'if row['kind']=='dir'else name;i=z.getinfo(key);b=z.read(key);assert len(b)==row['bytes']and sha(b)==row['sha256']and i.external_attr>>16==row['mode']
assert raw['complete_world_trees']==3
print(json.dumps({'status':'PASS_COMPACT_IDENTITY_ONLY_NOT_FULL_CONTINUATION_OR_FULL_RELEASE','manifest_files':len(m),'physical_files':len(m)+1,'client34_source_files':43,'server33_source_files':43,'native18_source_manifest_files':745,'each_source_wheel_payloads':244,'offline_dependency_wheels':20,'all8protected_scope_JSON_equal':True,'raw_ZIP_members':raw['ZIP_members'],'full_release':False}))
