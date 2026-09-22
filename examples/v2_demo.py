"""A reproducible V2 comparison on a new synthetic world, never the campaign.

Run: python3 -m examples.v2_demo --output /new/path
Every created fixture is labeled synthetic. Output includes a portable SQLite
file plus input JSON and inspectable contribution receipts/artifacts.
"""
import argparse
import copy
import json
from pathlib import Path
from kageyoni.engine import Engine, digest
from kageyoni.application import Application


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(destination):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    engine=Engine(destination/'synthetic.sqlite')
    try:
        def record(domain,id,**data):
            return dict(op='create',domain=domain,id=id,data=data,status='proposed',visibility='public',evidence=[{'note':'Synthetic V2 comparison, not campaign canon or measured production performance.'}])
        engine.apply(dict(api_version=3,branch='main',expected_revision=0,request_id='demo-world',kind='action',actor='fixture',narrative='Synthetic V2 test inputs',changes=[
            record('character','analyst',name='Example Analyst',entity_kind='person'),
            record('knowledge','comparison-observation',holder='analyst',assertion='Synthetic proposal: compare editing approaches using recorded time and satisfied checks.',attitude='believes'),
            record('resource','short-time',holder='analyst',name='Short edit time',quantity=20,unit='minutes'),
            record('resource','detailed-time',holder='analyst',name='Detailed edit time',quantity=40,unit='minutes'),
            record('resource','short-checks',holder='analyst',name='Short edit checks',quantity=3,unit='checks'),
            record('resource','detailed-checks',holder='analyst',name='Detailed edit checks',quantity=5,unit='checks')]))
        app=Application(engine,migrate_methods=True)
        node=app.nodes.bind('main','analyst','demo-node',1,{'note':'Synthetic comparison only'})['node_id']
        def ref(id):
            row=engine.get('main',id)
            return dict(domain=row['domain'],id=id,record_revision=row['version'],snapshot_hash=digest(row))
        definition=dict(name='Conserve editing time',operation={'kind':'constraint_rank','params':{'criteria':[{'field':'time','weight':1,'direction':'minimize','required':True}]}},
                        rationale='Try a recorded comparison procedure; no claim of mastery.',domains=['editing-plan'],
                        preconditions=['task_domain_matches','sources_current','claims_match_recorded_fields'],
                        failure_conditions=['missing_support','stale_source'],checking_procedure=['check_source_fields','recompute_scores'],
                        visibility='public',audience=[])
        source_refs=[ref('comparison-observation')]
        created=app.methods.create('main',node,'demo-method',1,definition,source_refs)
        mid=created['method_id']
        app.methods.assign('main',node,mid,1,'demo-assign',1,'experimental','Operator-authorized synthetic comparison')
        def claim(id,value):return {'value':value,'evidence':[{'source_ref':ref(id),'field_path':['data','quantity']}]}
        task=dict(task_id='choose-edit',revision=1,domain='editing-plan',objective='Compare two supplied editing options; speed and check count are separate preferences, not automatic quality.',source_refs=[ref(id) for id in ('short-time','detailed-time','short-checks','detailed-checks')],candidates=[
            {'id':'short','label':'Short edit','claims':{'time':claim('short-time',20),'checks':claim('short-checks',3)},'counterclaims':{}},
            {'id':'detailed','label':'Detailed edit','claims':{'time':claim('detailed-time',40),'checks':claim('detailed-checks',5)},'counterclaims':{}}])
        write(destination/'task.json',task)
        write(destination/'method-create.json',dict(node_id=node,request_id='demo-method',expected_world_revision=1,method=definition,source_refs=source_refs))
        def contribute(key):
            receipt=app.contributions.run('main','analyst',key,task)
            value=app.contributions.read('main',receipt['contribution_id'])
            write(destination/(key+'.json'),value)
            return value
        first=contribute('time-method')
        engine.apply(dict(api_version=3,branch='main',expected_revision=1,request_id='demo-rename',kind='action',actor='fixture',narrative='Synthetic display-name control',changes=[dict(op='patch',id='analyst',expected_version=1,data={'name':'Renamed Example'},evidence=[{'note':'Synthetic name-only control'}])]))
        renamed=contribute('renamed-node')
        para=copy.deepcopy(definition);para['name']='Prefer the option that takes fewer minutes';para['rationale']='Alternative wording of the same supplied operation.'
        app.methods.revise('main',node,mid,1,'demo-paraphrase',2,para,source_refs)
        app.methods.assign('main',node,mid,2,'demo-assign-paraphrase',2,'experimental','Same operation, different prose',expected_assignment_revision=1)
        paraphrased=contribute('paraphrased-method')
        changed=copy.deepcopy(para);changed['name']='Prioritize satisfied checks'
        changed['operation']['params']['criteria']=[{'field':'checks','weight':1,'direction':'maximize','required':True}]
        app.methods.revise('main',node,mid,2,'demo-revised-operation',2,changed,source_refs)
        app.methods.assign('main',node,mid,3,'demo-assign-operation',2,'experimental','Different explicit comparison criterion',expected_assignment_revision=2)
        revised=contribute('changed-operation')
        def ranks(value):
            return [r['candidate_id'] for r in value['result']['artifact']['content']['results'][0]['result']['ranked']]
        controls={'name_invariant':first['result']['artifact']['digest']==renamed['result']['artifact']['digest'],
                  'paraphrase_invariant':first['result']['artifact']['digest']==paraphrased['result']['artifact']['digest'],
                  'operation_changes_choice':ranks(first)==['short','detailed'] and ranks(revised)==['detailed','short']}
        assert all(controls.values()), controls
        summary=dict(controls=controls,synthetic=True,comparison='Mechanism proof only; not evidence of independent intelligence or creative advantage.',
                     method_versions=[1,2,3],
                     results={key:value['result'] for key,value in [('time',first),('renamed',renamed),('paraphrased',paraphrased),('changed',revised)]},verification=engine.verify())
        write(destination/'comparison.json',summary)
        return summary
    finally:engine.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,help='New directory; refuses existing paths')
    args=parser.parse_args();result=run(args.output)
    print(json.dumps({'synthetic':True,'saved_to':str(Path(args.output).resolve()),'verification':result['verification']},indent=2))

if __name__=='__main__':main()
