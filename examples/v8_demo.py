"""Execute scoped policy improvement and reversible activation on real artifacts."""
import base64
import hashlib
import json
from pathlib import Path
from kageyoni.engine import Engine
from kageyoni.operations import Operations
from kageyoni.persistence.migrations import install_all

def run(destination):
    root=Path(destination); root.mkdir(parents=True,exist_ok=False)
    engine=Engine(root/'daily.sqlite'); install_all(engine); ops=Operations(engine)
    valid=b'checked artifact'; oversized=b'larger artifact'
    def case(content,maximum):return {'content_base64':base64.b64encode(content).decode(),'max_bytes':maximum,'expected_sha256':hashlib.sha256(content).hexdigest()}
    proposal=ops.propose_policy('pipeline.write_file',{'check_order':['size','utf8','sha256']},'Reject excessive output before decoding it.')
    before=ops.check_artifact('pipeline.write_file',oversized,2,hashlib.sha256(oversized).hexdigest())
    trial=ops.trial_policy(proposal['event_id'],[case(valid,100),case(oversized,2)])
    activation=ops.activate_policy(proposal['event_id'],trial['event_id'])
    after=ops.check_artifact('pipeline.write_file',oversized,2,hashlib.sha256(oversized).hexdigest())
    ops.rollback_policy('pipeline.write_file',activation['event_id'])
    restored=ops.check_artifact('pipeline.write_file',oversized,2,hashlib.sha256(oversized).hexdigest())
    exported=ops.export_bundle(root/'portable.zip'); imported=Operations.import_bundle(root/'portable.zip',root/'reopened')
    summary={'trial':trial,'checks':{'trial_measures_fewer_checks':trial['candidate_checks']<trial['baseline_checks'],'activation_changes_runtime':after['checks']<before['checks'],'rollback_restores_execution':restored['checks']==before['checks'],'history_retained':len(ops._events('artifact_check'))==3,'portable_import_verified':imported['verified']},'export':exported,'limit':'A bounded artifact-validation ordering improvement, not proof of general intelligence or representative task advantage.'}
    assert all(summary['checks'].values())
    (root/'comparison.json').write_text(json.dumps(summary,indent=2)); engine.close(); return summary

if __name__=='__main__':
    import sys
    print(json.dumps(run(sys.argv[1]),indent=2))
