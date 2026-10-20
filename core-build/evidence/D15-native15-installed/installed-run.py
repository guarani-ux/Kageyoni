"""Native-only installed wheel qualification; no product/worker process claim."""
from pathlib import Path
import hashlib,json,sys,zipfile,subprocess,os,importlib.metadata
import pytest
import kageyoni.engine
import kageyoni.workspaces.worker_liveness
R=Path('/dev/shm/d15-native-installed');R.mkdir(exist_ok=False)
SOURCE=Path('/dev/shm/d15-product-integration/engine');WHEEL=Path('/dev/shm/d15-native-wheels/kageyoni_engine-11.1.0.dev15-py3-none-any.whl');SITE=Path(sys.prefix)/'lib/python3.12/site-packages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check():
 rows=[]
 with zipfile.ZipFile(WHEEL) as z:
  assert z.testzip() is None
  for n in z.namelist():
   if n.endswith('/') or not n.startswith(('kageyoni/','contracts/')):continue
   source=SOURCE/n
   if not source.exists() and n.startswith('kageyoni/data/'):source=SOURCE/Path(n).name
   b=z.read(n);assert source.read_bytes()==b==(SITE/n).read_bytes(),n
   rows.append({'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 origins=[]
 for name,m in sorted(sys.modules.items()):
  if name.split('.')[0] not in ('kageyoni','contracts'):continue
  paths=[m.__file__] if getattr(m,'__file__',None) else list(getattr(m,'__path__',[]))
  for p in paths:
   q=Path(p).resolve();assert q.is_relative_to(SITE),{'module':name,'origin':str(q)};origins.append({'module':name,'path':str(q)})
 assert importlib.metadata.version('kageyoni-engine')=='11.1.0.dev15'
 return {'version':'11.1.0.dev15','wheel_sha256':sha(WHEEL),'payloads':rows,'origins':origins}
before=check();(R/'before.json').write_text(json.dumps(before,indent=2)+'\n')
class Preservation:
 @pytest.hookimpl(hookwrapper=True,tryfirst=True)
 def pytest_runtest_teardown(self,item,nextitem):
  yield
  src=Path(os.environ['D15_NATIVE_EVIDENCE'])/item.name
  if not src.exists():return
  out=R/'specimen-zips'/(item.name+'.zip');out.parent.mkdir(exist_ok=True)
  cmd=[sys.executable,'-I','-B','/workspace/scratch/5c7ed9200168/resume-current/archive_closed_test_tree.py',str(src),str(out),'--release-redundant']
  p=subprocess.run(cmd,capture_output=True,text=True)
  with (R/'archive-log.jsonl').open('a') as f:f.write(json.dumps({'case':item.name,'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})+'\n')
  assert p.returncode==0,p.stderr
args=['-q','-x','-p','no:cacheprovider','--import-mode=prepend','-o','pythonpath=',str(SOURCE/'tests/test_worker_liveness.py'),str(SOURCE/'tests/test_liveness_review_countercases.py'),'--basetemp=/dev/shm/d15-native-installed-tmp','--junitxml='+str(R/'junit.xml')]
(R/'command.json').write_text(json.dumps({'args':args,'route':'Isolated fresh offline native-only venv. Installed package preloaded; pytest pythonpath empty; all imported native origins captured same process. No Samsara product imported, no OS worker or human qualification.'},indent=2)+'\n')
code=pytest.main(args,plugins=[Preservation()]);after=check();assert before['payloads']==after['payloads'];(R/'after.json').write_text(json.dumps(after,indent=2)+'\n');(R/'result.json').write_text(json.dumps({'pytest_exit_code':code,'native_payloads':len(after['payloads']),'wheel_sha256':sha(WHEEL),'source_wheel_installed_unchanged':True,'all_imported_native_modules_installed':True,'full_product_installed':False,'actual_worker_process_qualified':False,'full_release_qualified':False},indent=2)+'\n');raise SystemExit(code)
