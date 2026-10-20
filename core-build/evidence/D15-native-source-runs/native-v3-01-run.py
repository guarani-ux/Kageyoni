from pathlib import Path
import json,hashlib,sys,os
import pytest
import kageyoni.engine as engine
import kageyoni.workspaces.worker_liveness as worker
import kageyoni.workspaces.job_queue as queue
import kageyoni.persistence.migrations as migrations
root=Path(__file__).parent;expected=root/'engine'
origins={m.__name__:str(Path(m.__file__).resolve()) for m in [engine,worker,queue,migrations]}
assert all(Path(p).is_relative_to(expected) for p in origins.values()),origins
(root/'origins.json').write_text(json.dumps({'route':'complete isolated source, NOT installed qualification','modules':origins,'python':sys.executable,'pythonpath':os.environ['PYTHONPATH'],'source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in origins.values()}},indent=2)+'\n')
args=[str(root/'tests/test_worker_liveness.py'),str(root/'tests/test_liveness_review_countercases.py'),'-q','-p','no:cacheprovider','-o','pythonpath=','--basetemp='+str(root/'pytest-temp'),'--junitxml='+str(root/'native-v3-01.xml')]
(root/'command.json').write_text(json.dumps({'command':'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='+str(expected)+' TMPDIR='+str(root/'tmp')+' D15_NATIVE_EVIDENCE='+str(root/'specimens')+' resume-current/env-dev18/bin/python '+str(root/'run.py'),'pytest_args':args,'source_frozen_v3':True},indent=2)+'\n')
raise SystemExit(pytest.main(args))
