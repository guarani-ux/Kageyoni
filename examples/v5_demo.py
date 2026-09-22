"""Actual source-constrained document and checked world round trip; synthetic inputs."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from kageyoni.engine import Engine, digest
from kageyoni.application import Application
from kageyoni.persistence.migrations import install_workspaces

def setup(destination):
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    engine=Engine(root/'synthetic.sqlite')
    def record(domain,identifier,**data):return dict(op='create',domain=domain,id=identifier,status='proposed',visibility='public',evidence=[{'note':'Synthetic V5 fixture; no campaign event.'}],data=data)
    engine.apply(dict(api_version=3,branch='main',expected_revision=0,request_id='seed',kind='action',actor='fixture',narrative='Synthetic V5 world',changes=[
        record('character','maker',name='Workshop Fixture',entity_kind='person'),record('character','reader',name='Reader',entity_kind='person'),
        record('knowledge','method-source',holder='maker',assertion='Compare attention explicitly with evidence.',attitude='believes'),
        record('objective','unresolved',title='Unresolved fictional choice',phase='active',progress=0)]))
    install_workspaces(engine);app=Application(engine)
    node=app.nodes.bind('main','maker','node',1,{'note':'Synthetic only'})['node_id']
    source=engine.get('main','method-source')
    definition=dict(name='Attend to supported importance',rationale='A bounded comparison procedure.',domains=['planning'],operation={'kind':'constraint_rank','params':{'criteria':[{'field':'attention','weight':1,'direction':'maximize'}]}},
        preconditions=['sources_current'],failure_conditions=['stale_source'],checking_procedure=['check_source_fields','recompute_scores'],roles=['observer','evidence'],relationships=[{'source':'observer','relation':'attends_to','target':'evidence'}],visibility='public')
    method=app.methods.create('main',node,'method',1,definition,[{'domain':'knowledge','id':'method-source','record_revision':1,'snapshot_hash':digest(source)}])
    app.methods.assign('main',node,method['method_id'],1,'assign',1,'experimental','Synthetic comparison trial')
    transition=app.transitions.enter('main','maker','enter',source_ids=['maker','method-source','unresolved'])
    workspace=transition['workspace_id']
    content='Community audio workshops.\nFor new creators.\nPublish a teaser.\n2\n8\n'
    path=root/'brief-source.txt';path.write_bytes(content.encode('utf-8'))
    captured=app.documents.acquire_file(workspace,'capture',str(path),'studio', 'Synthetic Community Studio','Synthetic Community Studio',datetime.now(timezone.utc).isoformat())
    def cite(needle):
        start=content.index(needle);return dict(source_id='studio',revision=captured['revision'],digest=captured['digest'],start=start,end=start+len(needle))
    metrics={identifier:{'priority':{'value':value,'evidence':cite(str(value))}} for identifier,value in [('services',2),('audience',8)]}
    brief=dict(brief_id='brief-one',title='Community workshop draft',audience='New creators',purpose='Explain the supplied offering and identify missing scheduling evidence.',sections=[
        dict(id='services',heading='What is offered',field='offering',claims=[cite('Community audio workshops.')],metrics=metrics['services']),
        dict(id='audience',heading='Who it is for',field='audience',claims=[cite('For new creators.')],metrics=metrics['audience']),
        dict(id='schedule',heading='When it happens',field='schedule',claims=[],metrics={})],
        obligations=[dict(id='teaser',status='required',evidence=cite('Publish a teaser.'))])
    mapping=dict(destination_domain='document',roles={'observer':'editor','evidence':'material'},destination_roles=['editor','material'],destination_relationships=[{'source':'editor','relation':'attends_to','target':'material'}],field_map={'attention':'priority'})
    transfer=app.transfers.propose(workspace,method['method_id'],1,'transfer',mapping)
    cases=[dict(case_id='supported-order',candidates=[{'id':key,'metrics':value} for key,value in metrics.items()],expected_phase='completed',expected_order=['audience','services']),
           dict(case_id='missing-support',candidates=[{'id':'missing','metrics':{}}],expected_phase='blocked',expected_order=[])]
    return root,engine,app,dict(node_id=node,method=method,transition=transition,workspace_id=workspace,source=captured,brief=brief,mapping=mapping,transfer=transfer,cases=cases,cite=cite)

def run(destination):
    root,engine,app,fixture=setup(destination)
    try:
        before=app.documents.draft(fixture['workspace_id'],'untransferred',fixture['brief'])
        trial=app.transfers.run_trial(fixture['transfer']['transfer_id'],'destination-trial',fixture['cases'])
        drafted=app.documents.draft(fixture['workspace_id'],'transferred',fixture['brief'],transfer_trial_id=fixture['transfer']['transfer_id'])
        inquiry=app.documents.inquire(fixture['workspace_id'],'inquiry','What is offered, for whom, and when?',['offering','audience','schedule'],[
            {'field':'offering','evidence':fixture['cite']('Community audio workshops.')},{'field':'audience','evidence':fixture['cite']('For new creators.')}])
        draft_id=drafted['draft_id'];artifact_path=Path(drafted['artifact']['path']);artifact_path.unlink()
        engine.close();engine=Engine(root/'synthetic.sqlite');app=Application(engine)
        recovered=app.transitions.recover();reopened=app.documents.read(draft_id)
        returned=app.transitions.return_to_world(fixture['transition']['transition_id'],'return')
        checks=dict(actual_acquired_bytes=app.documents.source(fixture['workspace_id'],'studio')['text']==(root/'brief-source.txt').read_text(),
                    actual_method_changes_document=before['section_order']!=drafted['section_order'] and drafted['section_order'][:2]==['audience','services'],
                    checked_destination_trial=trial['status']=='qualified',unknown_schedule_preserved='schedule' in drafted['unknowns'] and 'Unknown: schedule' in drafted['text'],
                    brief_obligation_preserved=drafted['obligations'][0]['status']=='required',inquiry_reports_gap=inquiry['unknowns']==['schedule'],
                    artifact_recovered=artifact_path.exists() and reopened['text']==drafted['text'],exact_world_return=returned['world_unchanged'],
                    unresolved_choice_preserved=engine.get('main','unresolved')['data']['phase']=='active')
        assert all(checks.values()),checks
        report=dict(synthetic=True,checks=checks,draft=drafted,transition=returned,recovery=recovered,inquiry=inquiry,verification=engine.verify(),
            limit='Source-constrained drafting and bounded procedural transfer; semantic equivalence and audience effectiveness remain attributed judgments.')
        (root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');(root/'draft.md').write_text(reopened['text'],encoding='utf-8')
        return report
    finally:engine.close()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(run(args.output)['checks'],indent=2))
