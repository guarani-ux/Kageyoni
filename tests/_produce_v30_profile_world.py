"""Explicit installed-v30 producer for resource-profile migration tests.

Run with a separately pinned trusted old installed Python under -I. This file
contains no engine, SQL schema or world history; all worlds/jobs use real APIs.
It deliberately refuses a producer that installs31/32. No worker is launched.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--expected-runtime',required=True)
    parser.add_argument('--queued-job',action='store_true')
    args=parser.parse_args()
    from samsara.owner import Owner
    from samsara.content import definitions
    from samsara.protocol import PROTOCOL,runtime_fingerprint
    from kageyoni.engine import Engine
    import samsara.owner as product_module
    import kageyoni.engine as engine_module
    assert runtime_fingerprint()==args.expected_runtime,'Old producer runtime does not match explicit pin'
    owner=Owner(args.world,True,listen=False)
    result={}
    try:
        app=owner.app;engine=owner.engine;context,_=app.bind('operator')
        assert engine.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==30,'Producer is not a genuine v30 predecessor'
        assert not engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='activity_resource_profiles'").fetchone()
        assert not engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='activity_participants'").fetchone()
        serial=0
        def call(operation):
            nonlocal serial
            serial+=1
            response=app.handle(context,{'protocol':PROTOCOL,'request_id':'v30-profile-fixture:'+str(serial),
                'workspace_id':app.workspace_id,'branch':'main','expected_revision':app.revision(),'operation':operation})
            assert 'error' not in response,response
            return response
        source=call({'name':'workspace.view','limit':32,'cursor':None})['return']['source_refs'][0]
        job_id=None;old_queue=None
        if args.queued_job:
            d=next(d for d in definitions() if d['id']=='synthetic:real_work')
            call({'name':'activity.start','activity_id':'legacy-issued','kind':'real_work','definition':d['reference'],
                'parent_id':None,'participants':['visitor'],'purpose':'Explicit genuine v30 migration fixture.',
                'source_refs':[source],'acceptance_ref':'native:text_work/1'})
            call({'name':'job.enqueue','activity_id':'legacy-issued','recipe':'source_index',
                  'parameters':{'delay_seconds':0,'cpu_iterations':0},'max_seconds':10})
            job_id=app.store.get(app.workspace_id,'legacy-issued')['native']['job_id']
            old_queue=app.runner.queue.row(job_id)
            assert old_queue['state']=='queued' and old_queue['generation']==0 and old_queue['process_json'] is None
            changes=engine.db.total_changes
            assert app.runner.queue.enqueue(job_id,old_queue['binding_id'],old_queue['authority_epoch'],
                old_queue['recipe'],json.loads(old_queue['parameters_json']),old_queue['max_seconds'])==old_queue
            assert engine.db.total_changes==changes
        assert not app.runner.live
        result={'workspace_id':app.workspace_id,'runtime_digest':runtime_fingerprint(),'job_id':job_id,'queue_row':old_queue,
                'migration_max':30,'native_verify':engine.verify(),'direct_registry':engine.validate_registry(),
                'product_module':str(Path(product_module.__file__).resolve()),
                'product_module_sha256':hashlib.sha256(Path(product_module.__file__).read_bytes()).hexdigest(),
                'engine_module':str(Path(engine_module.__file__).resolve()),
                'engine_module_sha256':hashlib.sha256(Path(engine_module.__file__).read_bytes()).hexdigest(),
                'worker_launches':0,'queued_admission_replayed_without_writes':bool(args.queued_job)}
        assert result['direct_registry']['ok']
    finally:
        owner.close()
    # Independent actual old-native read-only reopen after the producer closes.
    closed=Engine(args.world/'world.sqlite',read_only=True)
    try:
        assert closed.verify()['ok'] and closed.validate_registry()['ok']
        assert closed.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==30
        if result['job_id']:
            row=dict(closed.db.execute('SELECT * FROM activity_queue WHERE job_id=?',(result['job_id'],)).fetchone())
            assert row==result['queue_row']
    finally:closed.close()
    result.update(database_sha256=hashlib.sha256((args.world/'world.sqlite').read_bytes()).hexdigest(),
                  metadata_sha256=hashlib.sha256((args.world/'workspace.json').read_bytes()).hexdigest(),
                  world=str(args.world.resolve()),producer_closed=True)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
