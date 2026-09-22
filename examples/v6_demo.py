"""Reproducible synthetic comparison: actual configured nodes, bodies and dissent."""
import argparse
import copy
import json
from pathlib import Path
from kageyoni.engine import Engine, digest
from kageyoni.application import Application
from kageyoni.persistence.migrations import install_network
from kageyoni.intelligence.network import Network


def make_drafts(engine):
    from kageyoni.workspaces.documents import Documents
    from kageyoni.workspaces.registry import Registry
    from kageyoni.persistence.artifacts import Artifacts
    from kageyoni.intelligence.transfer import Transfers
    app=Application(engine);documents=Documents(engine);transfers=Transfers(engine);artifacts=Artifacts(engine)
    drafts=[];workspaces=[];transfer_ids=[]
    text='Fast option 1. Careful option 5.'
    for character,field in [('speed','time'),('checks','checks')]:
        w=Registry(engine).open('main',character,'document','document-'+character,source_ids=[])
        workspaces.append(w['workspace_id'])
        method=app.methods.list('main',character)[0]
        transfer=transfers.propose(w['workspace_id'],method['method_id'],method['revision'],'transfer-'+character,
             {'destination_domain':'document','roles':{},'destination_roles':[],'destination_relationships':[],'field_map':{field:'metric'}})
        tid=transfer['transfer_id'];transfer_ids.append(tid)
        source=documents.ingest(w['workspace_id'],'source-'+character,'source-'+character,text,'synthetic-fixture','synthetic-fixture','2026-09-20T00:00:00+00:00')
        def span(start,end):return {'source_id':source['source_id'],'revision':source['revision'],'digest':source['digest'],'start':start,'end':end}
        first=span(0,text.index(' Careful'));second=span(text.index('Careful'),len(text))
        one=text.index('1');five=text.index('5')
        brief={'brief_id':'collective-brief','title':'Synthetic options','audience':'fixture reviewer','purpose':'Compare supplied ordering',
               'sections':[{'id':'fast','heading':'Fast','field':'option','required':True,'claims':[first],
                            'metrics':{'metric':{'value':1,'evidence':span(one,one+1)}}},
                           {'id':'careful','heading':'Careful','field':'option','required':True,'claims':[second],
                            'metrics':{'metric':{'value':5,'evidence':span(five,five+1)}}}], 'obligations':[]}
        candidates=[{'id':section['id'],'metrics':section['metrics']} for section in brief['sections']]
        cases=[{'case_id':'positive','candidates':candidates,'expected_phase':'completed','expected_order':['fast','careful'] if character=='speed' else ['careful','fast']},
               {'case_id':'negative','candidates':[{'id':'missing','metrics':{}}],'expected_phase':'blocked','expected_order':[]}]
        transfers.run_trial(tid,'trial-'+character,cases)
        receipt=documents.draft(w['workspace_id'],'draft-'+character,brief,transfer_trial_id=tid)
        drafts.append(documents.read(receipt['draft_id']))
    return drafts,workspaces,transfer_ids


def run(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    e=Engine(destination/'synthetic.sqlite')
    try:
        def record(domain,id,**data):
            return dict(op='create',domain=domain,id=id,data=data,status='proposed',visibility='public',evidence=[{'note':'Synthetic V6 fixture, not campaign canon.'}])
        e.apply(dict(api_version=3,branch='main',expected_revision=0,request_id='v6-world',kind='action',actor='fixture',narrative='Synthetic collective comparison',changes=[
            record('character','speed',name='Speed procedure',entity_kind='person'),
            record('character','checks',name='Check coverage procedure',entity_kind='person'),
            record('character','copy',name='Copied speed procedure',entity_kind='person'),
            record('character','unconfigured',name='Unconfigured fixture',entity_kind='person'),
            record('knowledge','source',holder='speed',assertion='Synthetic method evidence',attitude='believes'),
            record('resource','fast-time',holder='speed',name='Fast minutes',quantity=10,unit='minutes'),
            record('resource','careful-time',holder='speed',name='Careful minutes',quantity=20,unit='minutes'),
            record('resource','fast-checks',holder='speed',name='Fast checks',quantity=1,unit='checks'),
            record('resource','careful-checks',holder='speed',name='Careful checks',quantity=5,unit='checks')]))
        install_network(e);app=Application(e);network=Network(e)
        def ref(id):
            r=e.get('main',id);return dict(domain=r['domain'],id=id,record_revision=r['version'],snapshot_hash=digest(r))
        for character,field,direction in [('speed','time','minimize'),('checks','checks','maximize'),('copy','time','minimize'),('unconfigured',None,None)]:
            node=app.nodes.bind('main',character,'bind-'+character,1,{'note':'Synthetic configured node'})['node_id']
            if field is None:continue
            definition=dict(name='Fixture '+character,operation={'kind':'constraint_rank','params':{'criteria':[{'field':field,'weight':1,'direction':direction,'required':True}]}},
                            rationale='Synthetic comparison procedure',domains=['editing-plan'],preconditions=['task_domain_matches','sources_current','claims_match_recorded_fields'],
                            failure_conditions=['missing_support','stale_source'],checking_procedure=['check_source_fields','recompute_scores'],visibility='public',audience=[])
            m=app.methods.create('main',node,'method-'+character,1,definition,[ref('source')])
            app.methods.assign('main',node,m['method_id'],1,'assign-'+character,1,'experimental','Synthetic fixture procedure')
        def claim(id,value):return {'value':value,'evidence':[{'source_ref':ref(id),'field_path':['data','quantity']}]}
        task=dict(task_id='v6-compare',revision=1,domain='editing-plan',objective='Compare explicit speed and check coverage preferences.',source_refs=[ref(x) for x in ('fast-time','careful-time','fast-checks','careful-checks')],candidates=[
            {'id':'z-fast','claims':{'time':claim('fast-time',10),'checks':claim('fast-checks',1)},'counterclaims':{}},
            {'id':'a-careful','claims':{'time':claim('careful-time',20),'checks':claim('careful-checks',5)},'counterclaims':{}}])
        def participants(*names):return [{'character_id':x,'task':copy.deepcopy(task)} for x in names]
        single=network.run('main','single',participants('speed'))
        multi=network.run('main','multi',participants('speed','checks'))
        repeated=network.run('main','repeated',participants('speed','copy'))
        empty=network.run('main','empty',participants('unconfigured'))
        positive=network.compare('main',single['run_id'],multi['run_id'],['a-careful'])
        negative=network.compare('main',single['run_id'],multi['run_id'],['z-fast'])
        nohelp=network.compare('main',single['run_id'],repeated['run_id'],['z-fast'])
        lesson=network.record_coordination_lesson('main','review',single['run_id'],multi['run_id'],['a-careful'],'Fixture prefers checks; lexical tie break happens to choose careful. This is not independent quality evidence.','qualified')
        drafts,workspaces,transfer_ids=make_drafts(e)
        document_synthesis={'text':'# Operator compilation\n\n'+'\n\n'.join(d['text'] for d in drafts),
                            'uses':[{'draft_id':d['draft_id'],'quote':d['text']} for d in drafts],
                            'rationale':'Retain both source-constrained orderings and their differences. Authored compilation, not semantic quality proof.'}
        pending=network.compose('main','document-waiting',workspaces[0],[d['draft_id'] for d in drafts])
        composition=network.compose('main','document-compose',workspaces[0],[d['draft_id'] for d in drafts],document_synthesis)
        (destination/'document-composition.json').write_text(json.dumps(composition,indent=2)+'\n')
        (destination/'document-synthesis.md').write_text(document_synthesis['text'])
        summary={'synthetic':True,'single':single,'network':multi,'repeated':repeated,'blocked':empty,
                 'positive_criterion':positive,'negative_criterion':negative,'no_help':nohelp,'coordination_lesson':lesson,
                 'controls':{'different_methods_change_output':single['selected']!=multi['selected'],
                             'disagreement_retained':bool(multi['disagreements']),
                             'bodies_received':all(r['body'] for r in multi['bodies']),
                             'repetition_not_extra_calculation':repeated['unique_calculations']==1,
                             'no_eligible_is_blocked':empty['phase']=='blocked',
                             'network_can_be_worse':negative['single']['accepted'] and not negative['network']['accepted']},
                 'document_composition':composition,'document_handoff':pending,'verification':e.verify()}
        assert all(summary['controls'].values()),summary['controls']
        (destination/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
        (destination/'task.json').write_text(json.dumps(task,indent=2)+'\n')
        return summary
    finally:e.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(run(a.output)['controls'],indent=2))
