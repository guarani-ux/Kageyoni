"""Reproduce bounded learning on a separate synthetic world.

python3 -m examples.v3_demo --output NEW_DIRECTORY
The scripted observations and judgments are fixtures, not production outcomes.
"""
import argparse
import copy
import json
from pathlib import Path
from kageyoni.engine import Engine, digest
from kageyoni.application import Application


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def run(destination):
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    engine=Engine(root/'synthetic.sqlite')
    results={};serial=0
    try:
        def rec(domain,id,**data):
            return dict(op='create',domain=domain,id=id,data=data,status='proposed',visibility='public',evidence=[{'note':'Synthetic V3 fixture; not measured production performance or campaign canon.'}])
        def event(changes):
            nonlocal serial
            serial+=1
            return engine.apply(dict(api_version=3,branch='main',expected_revision=engine.branch('main')['revision'],request_id='fixture-event-'+str(serial),kind='action',actor='fixture',narrative='Synthetic V3 observation',changes=changes))
        def ref(id):
            row=engine.get('main',id)
            return dict(domain=row['domain'],id=id,record_revision=row['version'],snapshot_hash=digest(row))
        records=[rec('character','analyst',name='Learning Fixture',entity_kind='person'),rec('knowledge','method-source',holder='analyst',assertion='Synthetic initial approach: compare plans by recorded minutes.',attitude='believes')]
        values={'initial-fast':(10,2),'initial-thorough':(45,5),'later-fast':(20,2),'later-balanced':(30,5),'later-thorough':(60,6)}
        for candidate,(minutes,checks) in values.items():
            records.extend([rec('resource',candidate+'-time',holder='analyst',name=candidate+' minutes',quantity=minutes,unit='minutes'),rec('resource',candidate+'-checks',holder='analyst',name=candidate+' checks',quantity=checks,unit='checks')])
        event(records)
        app=Application(engine,migrate_learning=True)
        node=app.nodes.bind('main','analyst','demo-node',1,{'note':'Synthetic V3 only'})['node_id']
        base_method=dict(name='Use less time',rationale='Initial operator-authored comparison procedure.',domains=['editing-plan'],operation={'kind':'constraint_rank','params':{'criteria':[{'field':'time','weight':1,'direction':'minimize','required':True}]}},preconditions=['sources_current','claims_match_recorded_fields'],failure_conditions=['stale_source'],checking_procedure=['check_source_fields','recompute_scores'],visibility='public',audience=[])
        method=app.methods.create('main',node,'initial-method',1,base_method,[ref('method-source')])
        mid=method['method_id']
        app.methods.assign('main',node,mid,1,'initial-assignment',1,'experimental','Synthetic bounded trial')
        def task(id,candidates,context=None):
            citations=[];items=[]
            for candidate in candidates:
                claims={}
                for field,value in zip(('time','checks'),values[candidate]):
                    source=ref(candidate+'-'+field);citations.append(source)
                    claims[field]={'value':value,'evidence':[{'source_ref':source,'field_path':['data','quantity']}]}
                items.append({'id':candidate,'claims':claims,'counterclaims':{}})
            return dict(task_id=id,revision=1,domain='editing-plan',context=context if context is not None else {'purpose':'release'},objective='Compare recorded plan measurements; actual success requires a later observation.',candidates=items,source_refs=citations)
        initial_task=task('initial-trial',['initial-fast','initial-thorough'])
        later_task=task('later-trial',['later-fast','later-balanced','later-thorough'])
        unrelated=task('rough-cut-trial',['later-fast','later-balanced','later-thorough'],{'purpose':'rough-cut'})
        def contribute(name,current_task):
            receipt=app.contributions.run('main','analyst',name,current_task)
            value=app.contributions.read('main',receipt['contribution_id']);results[name]=value
            write(root/(name+'.json'),value);return value
        def outcome(name,value,status,rationale,number=0):
            event([rec('resource',name,holder='analyst',name=name,quantity=number,unit='fixture observation')])
            observation=dict(status=status,rationale=rationale,measurements=[{'value':number,'evidence':{'source_ref':ref(name),'field_path':['data','quantity']}}])
            payload=dict(branch='main',contribution_id=value['receipt']['contribution_id'],request_id='record-'+name,expected_world_revision=engine.branch('main')['revision'],observation=observation)
            write(root/(name+'-input.json'),payload)
            return app.learning.record_outcome(**payload)
        initial=contribute('initial-choice',initial_task)
        baseline=contribute('later-before-learning',later_task)
        initial_outcome=outcome('first-feedback',initial,'not_achieved','Fixture judgment: the selected quick edit omitted required checks. The scalar records an observed result, not proof of this interpretation.')
        lesson=dict(name='Attend to required checks',rationale='Proposed correction following the first observed shortfall; applicability remains a bounded hypothesis.',method_id=mid,method_revision=1,task_domain='editing-plan',context_conditions=[{'key':'purpose','equals':'release'}],operation_params={'criteria':[{'field':'checks','weight':1,'direction':'maximize','required':True}]},visibility='gm',audience=[])
        proposal_payload=dict(branch='main',node_id=node,request_id='propose-lesson',expected_world_revision=engine.branch('main')['revision'],lesson=lesson,outcome_ids=[initial_outcome['outcome_id']])
        write(root/'lesson-proposal-input.json',proposal_payload)
        proposed=app.learning.propose(**proposal_payload);lid=proposed['lesson_id']
        unqualified=contribute('later-proposed-only',later_task)
        review_payload=dict(branch='main',lesson_id=lid,lesson_revision=1,request_id='qualify-lesson',expected_world_revision=engine.branch('main')['revision'],status='qualified',rationale='Operator authorizes a bounded test of this corrective hypothesis.',expected_review_revision=0)
        write(root/'lesson-review-input.json',review_payload)
        app.learning.review(**review_payload)
        learned=contribute('later-with-qualified-lesson',later_task)
        different=contribute('unrelated-context',unrelated)
        # Reopen before another relevant task to prove durable application.
        engine.close();engine=Engine(root/'synthetic.sqlite');app=Application(engine)
        reopened=contribute('after-reopen',task('later-reopened',['later-fast','later-balanced','later-thorough']))
        contrary=outcome('contrary-feedback',learned,'not_achieved','Fixture judgment: maximizing checks alone overran the available editing time.')
        app.learning.review('main',lid,1,'contest-lesson',engine.branch('main')['revision'],'contested','The contrary outcome suspends this broad corrective rule.',expected_review_revision=1,counter_outcome_ids=[contrary['outcome_id']])
        contested=contribute('after-counterevidence',later_task)
        revised=copy.deepcopy(lesson);revised['name']='Compare both time and checks';revised['rationale']='Revision retains both shortfalls and tests an explicit tradeoff. Weights remain an operator choice, not learned truth.'
        revised['operation_params']['criteria'].append({'field':'time','weight':0.1,'direction':'minimize','required':True})
        app.learning.revise('main',node,lid,1,'revise-lesson',engine.branch('main')['revision'],revised,[initial_outcome['outcome_id']])
        app.learning.review('main',lid,2,'qualify-revision',engine.branch('main')['revision'],'qualified','Retain counterevidence and test the changed bounded procedure.',expected_review_revision=0)
        changed=contribute('after-qualified-revision',task('revision-trial',['later-fast','later-balanced','later-thorough']))
        def choice(value):return value['result']['artifact']['content']['results'][0]['result']['ranked'][0]['candidate_id']
        checks={'later_baseline_fast':choice(baseline)=='later-fast','proposal_has_no_effect':choice(unqualified)==choice(baseline),'qualified_lesson_changes_later_choice':choice(learned)=='later-thorough','irrelevant_context_unchanged':choice(different)=='later-fast','reopen_retains_application':choice(reopened)=='later-thorough','counterevidence_suspends_application':choice(contested)=='later-fast','revised_lesson_changes_choice':choice(changed)=='later-balanced','base_method_revision_unchanged':app.methods.read('main',mid)['revision']==1}
        assert all(checks.values()),checks
        summary=dict(synthetic=True,checks=checks,lesson_id=lid,node_id=node,method_id=mid,choices={name:choice(value) for name,value in results.items()},lesson=app.learning.read('main',lid),verification=engine.verify(),limit='Observed fixtures plus operator-authored interpretation demonstrate a reusable learning mechanism. They do not establish autonomous learning or practical advantage.')
        write(root/'later-task.json',later_task);write(root/'comparison.json',summary)
        return summary
    finally:engine.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();report=run(args.output)
    print(json.dumps({'synthetic':True,'checks':report['checks'],'saved_to':str(Path(args.output).resolve())},indent=2))

if __name__=='__main__':main()
