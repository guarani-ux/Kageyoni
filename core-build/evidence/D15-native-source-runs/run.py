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
(root/'native-v4-02-origins.json').write_text(json.dumps({'route':'complete isolated source, NOT installed qualification','modules':origins,'python':sys.executable,'pythonpath':os.environ['PYTHONPATH'],'source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in origins.values()}},indent=2)+'\n')
args=['/dev/shm/d15-repaired-native-run/tests/test_worker_liveness.py::test_old_epoch_stop_exit_but_no_renew_or_acceptance', '/dev/shm/d15-repaired-native-run/tests/test_worker_liveness.py::test_stop_exact_replay_cancel_dominance_and_observation', '/dev/shm/d15-repaired-native-run/tests/test_worker_liveness.py::test_normal_running_finish_boundary_and_explicit_exit', '/dev/shm/d15-repaired-native-run/tests/test_liveness_review_countercases.py::test_preregistered_stop_cannot_return', '/dev/shm/d15-repaired-native-run/tests/test_liveness_review_countercases.py::test_never_registered_stop_settles_without_invented_exit', '/dev/shm/d15-repaired-native-run/tests/test_liveness_review_countercases.py::test_retained_registered_identity_guards_illicitly_cleared_queue_process', '/dev/shm/d15-repaired-native-run/tests/test_liveness_review_countercases.py::test_normal_return_cannot_erase_missing_or_changed_registered_identity', '/dev/shm/d15-repaired-native-run/tests/test_liveness_review_countercases.py::test_matching_registered_identity_normal_return_remains_free_of_exit_receipt', '/dev/shm/d15-repaired-native-run/tests/test_liveness_review_countercases.py::test_explicit_cancel_dominates_nonpause_unregistered_stop_without_fake_exit', '-q', '-p', 'no:cacheprovider', '-o', 'pythonpath=', '--basetemp=/dev/shm/d15-repaired-native-run/pytest-temp-v4-02', '--junitxml=/dev/shm/d15-repaired-native-run/native-v4-02.xml']
(root/'native-v4-02-command.json').write_text(json.dumps({'command':'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='+str(expected)+' TMPDIR='+str(root/'tmp')+' D15_NATIVE_EVIDENCE='+str(root/'specimens')+' resume-current/env-dev18/bin/python '+str(root/'run.py'),'pytest_args':args,'source_version':'V4 diagnostic order only; V3 source preserved'},indent=2)+'\n')
raise SystemExit(pytest.main(args))
